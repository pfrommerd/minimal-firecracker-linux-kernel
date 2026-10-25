# Firecracker Minimal Linux Kernel - Docker Build

Build minimal, fast booting x86_64 and aarch64 Linux kernels for Firecracker inside Docker.
The builder runs on your Docker host’s CPU and uses cross-compilers as needed;
CPU emulation is not required.

## Quick Start

### Prerequisites
- docker

### Build the Kernel

```bash
make build
```
This builds both architectures sequentially. To build just one:

```bash
make build ARCH=x86_64
make build ARCH=aarch64
```

Or build one architecture directly with Docker (`TARGET_ARCH` defaults to `x86_64`):

```bash
mkdir -p kernel-output
docker build --build-arg TARGET_ARCH=aarch64 -t firecracker-kernel-builder:latest-aarch64 .
docker run --rm -v "$(pwd)/kernel-output:/output-mount" firecracker-kernel-builder:latest-aarch64
```

### Output

After building, you'll find:
```
kernel-output/
├── vmlinux-6.18.58-firecracker-minimal-x86_64  # Uncompressed ELF image
├── Image-6.18.58-firecracker-minimal-aarch64   # Uncompressed ARM64 boot image
├── config-6.18.58-x86_64                      # Resolved x86 kernel config
└── config-6.18.58-aarch64                     # Resolved ARM kernel config
```

## Files in This Directory

- `Dockerfile` - Docker image for building the kernel
- `firecracker-minimal-x86_64.config` / `firecracker-minimal-aarch64.config` - Architecture-specific minimal kernel configurations
- `scripts/build-kernel.sh` - Toolchain selection, configuration checks, and image export
- `.github/workflows/build.yml` - Automated GitHub Actions build

## GitHub Releases

Push a tag starting with `v` to build the tagged commit and publish a release:

```bash
git tag v1.0.0
git push origin v1.0.0
```

The workflow builds each architecture on a matching Ubuntu runner and uses the
kernel version configured in the Makefile. The release tag does not override that
version. Both builds must succeed before the release job runs. It validates that
both images are nonempty and have matching versions, then uploads exactly two assets:

- `vmlinux-<kernel-version>-firecracker-minimal-x86_64`
- `Image-<kernel-version>-firecracker-minimal-aarch64`

The x86 asset now includes `-x86_64`; update download URLs that use the previous
filename. Kernel configs and an initramfs are not included in the release.

The release is published with generated notes after both kernels upload
successfully. If uploading or publishing fails, rerun the workflow to finish the
draft release. An already published release causes the workflow to fail without
changing it. Authentication uses the built-in `GITHUB_TOKEN`; no additional
secrets are required.

## Usage

### Basic Build
```bash
make build
```

Output: both kernel images and their resolved configs in `kernel-output/`.

### Choose Output Directory or Open a Build Shell

```bash
make build OUTPUT_DIR=/tmp/firecracker-kernels
make shell ARCH=aarch64
```

Relative and absolute output paths are supported. Build the selected architecture
before opening its shell, and pass the same `KERNEL_VERSION` if you overrode it.
The shell has the matching kernel `ARCH` and `CROSS_COMPILE` exported.

### Build Different Kernel Version
```bash
make build KERNEL_VERSION=6.1.1
```

## Using the Kernel with Firecracker

Use the image matching your Firecracker host’s architecture. Firecracker uses
`vmlinux` on x86_64 and `arch/arm64/boot/Image` on aarch64; see the
[upstream kernel build guide](https://github.com/firecracker-microvm/firecracker/blob/main/docs/rootfs-and-kernel-setup.md).

### Sample Firecracker Config

Create `config.json`:
```json
{
  "boot-source": {
    "kernel_image_path": "/path/to/kernel-output/vmlinux-6.18.58-firecracker-minimal-x86_64",
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

For aarch64, set `kernel_image_path` to
`/path/to/kernel-output/Image-6.18.58-firecracker-minimal-aarch64` and use an
ARM64 root filesystem. For example, use these boot arguments (the serial console
is also `ttyS0` on Firecracker ARM guests):

```text
console=ttyS0 reboot=k panic=1 random.trust_cpu=on root=/dev/vda rw ip=172.17.0.101::172.17.0.1:255.255.255.0::eth0:off
```

### Start Firecracker
```bash
firecracker --api-sock /tmp/firecracker.sock --config-file config.json
```

## Performance

**Original x86 boot-time target:** ~100-120ms with networking, ~90-95ms without.
ARM boot performance has not been measured.

## Validation

Run the command-routing and release-guard tests without Docker or GitHub access:

```bash
python3 -m unittest discover -s tests -v
```

These tests also run before each CI build. Kernel builds check required resolved
config settings and the linked image’s architecture. Boot validation requires a
Linux host with KVM, Firecracker, and a root filesystem matching each architecture.
