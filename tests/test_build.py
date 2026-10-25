"""Exercise Docker command routing and release guards without Docker or GitHub.

Run with: python3 -m unittest discover -s tests -v
"""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.log = self.work / "commands.jsonl"
        self.env = dict(os.environ, PATH=f"{self.work}:{os.environ['PATH']}",
                        COMMAND_LOG=str(self.log))
        self.env.pop('ARCH', None)

    def mock(self, name, body):
        path = self.work / name
        path.write_text("#!/usr/bin/env python3\n" + textwrap.dedent(body))
        path.chmod(0o755)

    def commands(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def test_architecture_selection_and_output_paths(self):
        self.mock("docker", """
            import json, os, sys
            with open(os.environ['COMMAND_LOG'], 'a') as log:
                log.write(json.dumps(sys.argv[1:]) + '\\n')
        """)
        for selection, expected in [(None, ['x86_64', 'aarch64']),
                                    ('x86_64', ['x86_64']), ('aarch64', ['aarch64'])]:
            with self.subTest(arch=selection):
                self.log.write_text('')
                # Also exercise relative paths, absolute paths, and spaces.
                output = self.work / 'kernel output'
                output_arg = str(output) if selection else os.path.relpath(output, ROOT)
                args = ['make', 'build', 'KERNEL_VERSION=6.1.1', f'OUTPUT_DIR={output_arg}']
                if selection:
                    args.append(f'ARCH={selection}')
                result = subprocess.run(args, cwd=ROOT, env=self.env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                commands = self.commands()
                self.assertEqual([c[0] for c in commands], ['build', 'run'] * len(expected))
                for arch, build, run in zip(expected, commands[::2], commands[1::2]):
                    self.assertIn(f'TARGET_ARCH={arch}', build)
                    self.assertIn('KERNEL_VERSION=6.1.1', build)
                    self.assertIn(f'firecracker-kernel-builder:6.1.1-{arch}', build)
                    self.assertIn(f'{output}:/output-mount', run)
                    self.assertEqual(run[-1], f'firecracker-kernel-builder:6.1.1-{arch}')

    def test_invalid_selection_and_build_failure_stop_docker_calls(self):
        self.mock('docker', """
            import json, os, sys
            with open(os.environ['COMMAND_LOG'], 'a') as log:
                log.write(json.dumps(sys.argv[1:]) + '\\n')
            sys.exit(1 if sys.argv[1] == os.environ.get('FAIL_DOCKER', 'build') else 0)
        """)
        for args in [['build', 'ARCH=invalid'], ['shell', 'ARCH=all']]:
            result = subprocess.run(['make', *args], cwd=ROOT, env=self.env, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(self.commands(), [])
        for failure, expected in [('build', ['build']), ('run', ['build', 'run'])]:
            with self.subTest(failure=failure):
                self.log.write_text('')
                result = subprocess.run(['make', 'build', f'OUTPUT_DIR={self.work}/output'],
                                        cwd=ROOT, env=dict(self.env, FAIL_DOCKER=failure),
                                        capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual([c[0] for c in self.commands()], expected)

    def test_release_publication_guards(self):
        workflow = (ROOT / '.github/workflows/build.yml').read_text()
        publish = workflow.split('      - name: Publish kernel release\n', 1)[1]
        script = textwrap.dedent(publish.split('        run: |\n', 1)[1])
        self.mock('gh', """
            import json, os, sys
            with open(os.environ['COMMAND_LOG'], 'a') as log:
                log.write(json.dumps(sys.argv[1:]) + '\\n')
            command = sys.argv[2]
            state = os.environ['RELEASE_STATE']
            if command == 'view':
                if state == 'missing':
                    sys.exit(1)
                print('false' if state == 'published' else 'true')
            if command == os.environ.get('FAIL_COMMAND'):
                sys.exit(1)
        """)
        scenarios = [
            ('new release', 'missing', 'valid', '', ['view', 'create', 'upload', 'edit'], True),
            ('retry draft', 'draft', 'valid', '', ['view', 'upload', 'edit'], True),
            ('published', 'published', 'valid', '', ['view'], False),
            ('upload fails', 'draft', 'valid', 'upload', ['view', 'upload'], False),
            ('create fails', 'missing', 'valid', 'create', ['view', 'create'], False),
            ('publish fails', 'draft', 'valid', 'edit', ['view', 'upload', 'edit'], False),
            ('missing ARM', 'draft', 'missing', '', [], False),
            ('empty ARM', 'draft', 'empty', '', [], False),
            ('version mismatch', 'draft', 'mismatch', '', [], False),
            ('duplicate x86', 'draft', 'duplicate', '', [], False),
        ]
        for name, state, images, failure, expected, success in scenarios:
            with self.subTest(scenario=name):
                case = self.work / name
                output = case / 'kernel-output'
                output.mkdir(parents=True)
                x86 = output / 'vmlinux-6.18.58-firecracker-minimal-x86_64'
                x86.write_bytes(b'kernel')
                arm_version = '6.1.1' if images == 'mismatch' else '6.18.58'
                arm = output / f'Image-{arm_version}-firecracker-minimal-aarch64'
                if images != 'missing':
                    arm.write_bytes(b'' if images == 'empty' else b'kernel')
                if images == 'duplicate':
                    (output / 'vmlinux-6.1.1-firecracker-minimal-x86_64').write_bytes(b'kernel')
                self.log.write_text('')
                env = dict(self.env, RELEASE_STATE=state, FAIL_COMMAND=failure, RELEASE_TAG='v1.0.0')
                result = subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', script],
                                        cwd=case, env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode == 0, success, result.stderr)
                commands = self.commands()
                self.assertEqual([c[1] for c in commands], expected)
                for command in commands:
                    if command[1] == 'upload':
                        self.assertEqual(command[3:], [str(x86.relative_to(case)),
                                                      str(arm.relative_to(case)), '--clobber'])

    def test_sapphire_features_are_built_in_and_checked(self):
        required = "CGROUPS CGROUP_SCHED CFS_BANDWIDTH MEMCG CGROUP_PIDS CGROUP_BPF SECCOMP SECCOMP_FILTER VSOCKETS VIRTIO_VSOCKETS VETH NETFILTER NF_CONNTRACK NF_NAT NF_TABLES NFT_CT NFT_NAT NFT_MASQ OVERLAY_FS BLK_DEV_LOOP EXT4_FS_SECURITY".split()
        script = (ROOT / 'scripts/build-kernel.sh').read_text()
        for arch in ['x86_64', 'aarch64']:
            config = (ROOT / f'firecracker-minimal-{arch}.config').read_text().splitlines()
            for setting in required:
                self.assertIn(f'CONFIG_{setting}=y', config)
                self.assertIn(setting, script)
        arm = (ROOT / 'firecracker-minimal-aarch64.config').read_text()
        self.assertIn('CONFIG_SERIAL_AMBA_PL011_CONSOLE=y', arm)

    def test_shell_toolchain_selection(self):
        for arch, kernel_arch, compiler in [('x86_64', 'x86', 'x86_64-linux-gnu-'),
                                            ('aarch64', 'arm64', 'aarch64-linux-gnu-')]:
            with self.subTest(arch=arch):
                result = subprocess.run(['sh', str(ROOT / 'scripts/build-kernel.sh'), '--shell'],
                                        env=dict(self.env, TARGET_ARCH=arch),
                                        input='printf "%s %s" "$ARCH" "$CROSS_COMPILE"\n',
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, f'{kernel_arch} {compiler}')


if __name__ == '__main__':
    unittest.main()
