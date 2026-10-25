# Docker-based builds run on the host CPU; toolchains select the guest CPU.
KERNEL_VERSION ?= 6.18.58
OUTPUT_DIR ?= ./kernel-output
IMAGE_NAME ?= firecracker-kernel-builder
ARCH ?= all

SUPPORTED_ARCHES := x86_64 aarch64
ifeq ($(ARCH),all)
BUILD_ARCHES := $(SUPPORTED_ARCHES)
else
BUILD_ARCHES := $(ARCH)
endif

.PHONY: help build clean rebuild shell check-config check-arch

help:
	@echo "Firecracker Minimal Kernel Builder"
	@echo ""
	@echo "  make build       - Build both architectures (kernel $(KERNEL_VERSION))"
	@echo "  make rebuild     - Clean, then build"
	@echo "  make clean       - Remove output directory"
	@echo "  make shell ARCH=x86_64 - Open the selected build container"
	@echo ""
	@echo "Options: ARCH=all|x86_64|aarch64, KERNEL_VERSION=X.X.X, OUTPUT_DIR=path"

check-arch:
	@case "$(ARCH)" in all|x86_64|aarch64) ;; \
		*) echo "Error: ARCH must be all, x86_64, or aarch64." >&2; exit 1 ;; esac

check-config: check-arch
	@for arch in $(BUILD_ARCHES); do \
		if [ ! -f "firecracker-minimal-$$arch.config" ]; then \
			echo "Error: firecracker-minimal-$$arch.config not found!" >&2; exit 1; \
		fi; \
	done

build: check-config
	@mkdir -p "$(OUTPUT_DIR)"
	@set -e; output_dir=$$(cd "$(OUTPUT_DIR)" && pwd); \
	for arch in $(BUILD_ARCHES); do \
		echo "Building kernel $(KERNEL_VERSION) for $$arch..."; \
		docker build \
			--build-arg KERNEL_VERSION="$(KERNEL_VERSION)" \
			--build-arg TARGET_ARCH="$$arch" \
			-t "$(IMAGE_NAME):$(KERNEL_VERSION)-$$arch" \
			-t "$(IMAGE_NAME):latest-$$arch" .; \
		docker run --rm \
			-v "$$output_dir:/output-mount" \
			"$(IMAGE_NAME):$(KERNEL_VERSION)-$$arch"; \
	done
	@echo "=== Build Complete ==="
	@ls -lh "$(OUTPUT_DIR)/"

# Keep clean and build ordered even under make -j.
rebuild:
	$(MAKE) clean
	$(MAKE) build

clean:
	@echo "Cleaning output directory..."
	rm -rf "$(OUTPUT_DIR)"

shell: check-config
	@if [ "$(ARCH)" = all ]; then \
		echo "Error: select ARCH=x86_64 or ARCH=aarch64 for make shell." >&2; exit 1; \
	fi
	docker run --rm -it \
		-v "$(CURDIR)/firecracker-minimal-$(ARCH).config:/build/linux-$(KERNEL_VERSION)/.config" \
		"$(IMAGE_NAME):$(KERNEL_VERSION)-$(ARCH)" \
		/bin/sh /usr/local/bin/build-kernel --shell

.DEFAULT_GOAL := build
