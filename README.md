# Firecracker Minimal Linux Kernel - Docker Build

Build a minimal, fast booting Linux kernel for Firecracker, build inside Docker

## Quick Start

### Prerequisites
- docker

### Build the Kernel

```bash
make build
```
or
```bash
docker build -t firecracker-kernel-builder .
docker run --rm -v $(pwd)/kernel-output:/output-mount firecracker-kernel-builder:latest
```

### Output

After building, you'll find:
```
kernel-output/
├── vmlinux-6.18.58-firecracker-minimal   # The kernel image (uncompressed)
└── config-6.18.58                        # The kernel config used
```

## Files in This Directory

- `Dockerfile` - Docker image for building the kernel
- `firecracker-minimal.config` - Minimal kernel configuration, works for the 6.x kernel
- `.github/workflows/build.yml` - Automated GitHub Actions build

## GitHub Releases

Push a tag starting with `v` to build the tagged commit and publish a release:

```bash
git tag v1.0.0
git push origin v1.0.0
```

The workflow runs `make build` on an x86_64 Ubuntu runner and uses the kernel
version configured in the Makefile. The release tag does not override that version.
The only uploaded asset is `vmlinux-<kernel-version>-firecracker-minimal`;
the kernel config and an initramfs are not included.

The release is published with generated notes after the kernel builds and uploads
successfully. If uploading or publishing fails, rerun the workflow to finish the
draft release. An already published release causes the workflow to fail without
changing it. Authentication uses the built-in `GITHUB_TOKEN`; no additional
secrets are required.

## Usage

### Basic Build
```bash
make build
```

Output: `kernel-output/vmlinux-6.18.58-firecracker-minimal`

### Build Different Kernel Version
```bash
make build KERNEL_VERSION=6.1.1
```

## Using the Kernel with Firecracker

### Sample Firecracker Config

Create `config.json`:
```json
{
  "boot-source": {
    "kernel_image_path": "/path/to/kernel-output/vmlinux-6.18.58-firecracker-minimal",
    "boot_args": "console=ttyS0 reboot=k panic=1 pci=off random.trust_cpu=on root=/dev/vda rw i8042.noaux i8042.nomux i8042.nopnp i8042.dumbkbd ip=172.17.0.101::172.17.0.1:255.255.255.0::eth0:off"
  },
  "drives": [
    {
      "drive_id": "rootfs",
      "path_on_host": "/path/to/rootfs.ext4",
      "is_root_device": true,
      "is_read_only": false
    }
  ],
  "machine-config": {
    "vcpu_count": 2,
    "mem_size_mib": 512
  }
}
```

### Start Firecracker
```bash
firecracker --api-sock /tmp/firecracker.sock --config-file config.json
```

## Performance

**Expected kernel boot time:** ~100-120ms with networking, ~90-95ms without
