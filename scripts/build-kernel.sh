#!/bin/sh
set -eu

case "$TARGET_ARCH" in
    x86_64)
        export ARCH=x86 CROSS_COMPILE=x86_64-linux-gnu-
        target=vmlinux
        image=vmlinux
        machine='Advanced Micro Devices X86-64'
        required='X86_64 PVH KVM_GUEST'
        ;;
    aarch64)
        export ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu-
        target=Image
        image=arch/arm64/boot/Image
        machine=AArch64
        required='ARM64 ARM64_4K_PAGES ARM_GIC ARM_ARCH_TIMER SERIAL_OF_PLATFORM RTC_DRV_PL031'
        ;;
    *) echo "Unsupported TARGET_ARCH: $TARGET_ARCH" >&2; exit 1 ;;
esac

if [ "${1:-}" = --shell ]; then
    exec /bin/bash
fi

make olddefconfig
# Fail if Kconfig dropped a required built-in driver or architecture setting.
for option in $required VIRTIO_MMIO VIRTIO_BLK VIRTIO_NET EXT4_FS \
    SERIAL_8250_CONSOLE PRINTK DEVTMPFS DEVTMPFS_MOUNT BINFMT_ELF; do
    if ! grep -qx "CONFIG_$option=y" .config; then
        echo "Missing required setting CONFIG_$option=y for $TARGET_ARCH" >&2
        exit 1
    fi
done

make -j"$(nproc)" "$target"
LC_ALL=C "${CROSS_COMPILE}readelf" -h vmlinux | grep -F "$machine"
test -s "$image"
mkdir -p /output
cp "$image" "/output/$target-$KERNEL_VERSION-firecracker-minimal-$TARGET_ARCH"
cp .config "/output/config-$KERNEL_VERSION-$TARGET_ARCH"
ls -lh /output/
