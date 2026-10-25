FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Both toolchains run on the container's native CPU, including on Apple Silicon.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc-x86-64-linux-gnu \
    gcc-aarch64-linux-gnu \
    bc \
    bison \
    flex \
    libelf-dev \
    libssl-dev \
    ca-certificates \
    wget \
    xz-utils \
    && rm -rf /var/lib/apt/lists/*

ARG KERNEL_VERSION=6.18.58
ARG TARGET_ARCH=x86_64
ENV KERNEL_VERSION=${KERNEL_VERSION} TARGET_ARCH=${TARGET_ARCH}

RUN case "$TARGET_ARCH" in x86_64|aarch64) ;; \
    *) echo "Unsupported TARGET_ARCH: $TARGET_ARCH" >&2; exit 1 ;; esac

WORKDIR /build
RUN wget https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-${KERNEL_VERSION}.tar.xz && \
    tar xf linux-${KERNEL_VERSION}.tar.xz && \
    rm linux-${KERNEL_VERSION}.tar.xz

WORKDIR /build/linux-${KERNEL_VERSION}
COPY firecracker-minimal-${TARGET_ARCH}.config .config
COPY scripts/build-kernel.sh /usr/local/bin/build-kernel
RUN /bin/sh /usr/local/bin/build-kernel

CMD ["sh", "-ec", "test -d /output-mount || { echo 'Mount a volume to /output-mount to extract the kernel' >&2; exit 1; }; cp /output/* /output-mount/; echo 'Kernel copied to /output-mount/'"]
