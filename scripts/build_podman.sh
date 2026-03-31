#!/bin/bash
# =============================================================================
# openSUSE AI Assistant - Container Build Script
# Platform: openSUSE Leap 16 | Python 3.13
# Builds the suse-ai image with Podman or Docker
# Usage: ./scripts/build_podman.sh [--docker | --podman] [--no-cache] [--push]
# =============================================================================
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; NC='\033[0m'
log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()  { echo -e "${BLUE}[STEP]${NC} $1"; }

# ─── Defaults ────────────────────────────────────────────────────────────────
ENGINE="podman"
IMAGE_NAME="suse-ai"
IMAGE_TAG="latest"
NO_CACHE=""
PUSH=false

# Get absolute paths based on script location (scripts/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ─── Parse Arguments ─────────────────────────────────────────────────────────
for arg in "$@"; do
    case $arg in
        --docker)    ENGINE="docker" ;;
        --podman)    ENGINE="podman" ;;
        --no-cache)  NO_CACHE="--no-cache" ;;
        --push)      PUSH=true ;;
        --help)
            echo "Usage: ./scripts/build_podman.sh [--docker|--podman] [--no-cache] [--push]"
            echo ""
            echo "Options:"
            echo "  --docker     Use Docker instead of Podman"
            echo "  --podman     Use Podman (default)"
            echo "  --no-cache   Build without cache"
            echo "  --push       Push image after build"
            exit 0
            ;;
        *)
            log_error "Unknown argument: $arg"
            exit 1
            ;;
    esac
done

# ─── Detect Engine & Paths ───────────────────────────────────────────────────
if [[ "$ENGINE" == "podman" ]]; then
    if ! command -v podman &>/dev/null; then
        log_error "podman not found. Install: sudo zypper install -y podman"
        exit 1
    fi
    # Set paths specific to podman
    CONTAINERFILE="deploy/podman/Containerfile"
    COMPOSE_CMD="podman compose -f deploy/podman/compose.yaml"
else
    if ! command -v docker &>/dev/null; then
        log_error "docker not found. Install: sudo zypper install -y docker-ce"
        exit 1
    fi
    if ! docker info &>/dev/null 2>&1; then
        log_error "Docker daemon not running. Start: sudo systemctl start docker"
        exit 1
    fi
    # Set paths specific to docker
    CONTAINERFILE="deploy/docker/Dockerfile"
    COMPOSE_CMD="docker compose -f deploy/docker/docker-compose.yml"
fi

# ─── Pre-flight Checks ───────────────────────────────────────────────────────
log_step "Pre-flight checks"

if command -v python3.13 &>/dev/null; then
    log_info "python3.13 $(python3.13 --version 2>&1 | awk '{print $2}')"
else
    log_warn "python3.13 not found locally (OK if building inside container)"
fi

if [[ ! -f "${PROJECT_DIR}/${CONTAINERFILE}" ]]; then
    log_error "Build file not found at ${PROJECT_DIR}/${CONTAINERFILE}"
    exit 1
fi
log_info "Build file: ${PROJECT_DIR}/${CONTAINERFILE}"

if [[ ! -f "${PROJECT_DIR}/requirements.txt" ]]; then
    log_error "requirements.txt not found at ${PROJECT_DIR}/requirements.txt"
    exit 1
fi
log_info "requirements.txt: ${PROJECT_DIR}/requirements.txt"

# ─── Build ───────────────────────────────────────────────────────────────────
log_step "Building ${IMAGE_NAME}:${IMAGE_TAG} with ${ENGINE}..."
log_info "Project directory: ${PROJECT_DIR}"

# Move to the root project directory so the build context (.) includes all files (src/, requirements.txt, etc)
cd "${PROJECT_DIR}"

BUILD_START=$(date +%s)

${ENGINE} build \
    -t "${IMAGE_NAME}:${IMAGE_TAG}" \
    -t "${IMAGE_NAME}:build-$(date +%Y%m%d)" \
    -f "${CONTAINERFILE}" \
    ${NO_CACHE} \
    .

BUILD_RC=$?
BUILD_END=$(date +%s)
BUILD_TIME=$((BUILD_END - BUILD_START))

if [[ $BUILD_RC -eq 0 ]]; then
    log_info "Build completed in ${BUILD_TIME}s"
else
    log_error "Build failed after ${BUILD_TIME}s"
    exit 1
fi

# ─── Verify ──────────────────────────────────────────────────────────────────
log_step "Verifying image..."
${ENGINE} images "${IMAGE_NAME}" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedSince}}"

# ─── Push (optional) ─────────────────────────────────────────────────────────
if [[ "$PUSH" == true ]]; then
    log_step "Pushing ${IMAGE_NAME}:${IMAGE_TAG}..."
    ${ENGINE} push "${IMAGE_NAME}:${IMAGE_TAG}"
fi

# ─── Summary ─────────────────────────────────────────────────────────────────
echo ""
log_info "Build successful!"
echo ""
IMAGE_SIZE=$(${ENGINE} image inspect "${IMAGE_NAME}:${IMAGE_TAG}" \
    --format '{{.Size}}' 2>/dev/null || echo 'unknown')
echo "  Image: ${ENGINE}://${IMAGE_NAME}:${IMAGE_TAG}"
echo "  Size:  ${IMAGE_SIZE}"
echo ""
echo "  Run with ${ENGINE} Compose:"
echo "    ${COMPOSE_CMD} up -d"
echo ""
echo "  Or directly:"
echo "    ${ENGINE} run -it --rm --userns=keep-id \\"
echo "      -p 8090:8090 \\"
echo "      -v /var/lib/suse-ai:/data:rw,z \\"
echo "      ${IMAGE_NAME}:${IMAGE_TAG}"
