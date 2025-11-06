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
├── vmlinux-6.8.12-firecracker-minimal    # The kernel image (uncompressed)
└── config-6.8.12                         # The kernel config used
```

## Files in This Directory

- `Dockerfile` - Docker image for building the kernel
- `firecracker-minimal.config` - Minimal kernel configuration, works for the 6.x kernel
- `build-docker.sh` - Automated build script

## Usage

### Basic Build
```bash
make build
```

Output: `kernel-output/vmlinux-6.8.12-firecracker-minimal`

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
    "kernel_image_path": "/path/to/kernel-output/vmlinux-6.8.12-firecracker-minimal",
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
