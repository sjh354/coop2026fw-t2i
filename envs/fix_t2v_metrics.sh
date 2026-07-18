#!/usr/bin/env bash
# t2v-metrics==3.0 workarounds for t2i-score env.
#
# t2v_metrics/__init__.py unconditionally imports every VLM backend it bundles
# (LLaVA-OneVision/-Video, InternVideo2, ...) even though src/scoring.py only
# uses VQAScore(model="clip-flant5-xl"). Those unused backends pull in heavy
# deps we don't need (llava, flash_attn) and a CUDA-version-mismatched
# torchaudio wheel. Run this once, after `pip install ... t2v-metrics==3.0`,
# inside the target conda env.
#
#     conda activate t2i-score
#     bash envs/fix_t2v_metrics.sh
set -euo pipefail

SP="$(python -c 'import site; print(site.getsitepackages()[0])')"

# 1) torchaudio pulled by t2v-metrics defaults to a non-cu121 wheel and
#    mismatches the cu121 torch installed earlier -> crashes on import.
pip install torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cu121 \
    --force-reinstall --no-deps

# 2) Minimal `llava` stub so LLaVA-OneVision/-Video imports succeed without
#    actually vendoring/installing LLaVA-NeXT (we never instantiate those
#    model classes — only clip-flant5-xl).
mkdir -p "$SP/llava/model"
: > "$SP/llava/__init__.py"
: > "$SP/llava/model/__init__.py"
cat > "$SP/llava/model/builder.py" <<'EOF'
def load_pretrained_model(*args, **kwargs):
    raise NotImplementedError(
        "llava is stubbed in this env — only present to satisfy t2v_metrics' "
        "unconditional import of LLaVA-OneVision/-Video. Install real LLaVA "
        "(LLaVA-NeXT) if you actually need those model variants."
    )
EOF
cat > "$SP/llava/mm_utils.py" <<'EOF'
def process_images(*args, **kwargs):
    raise NotImplementedError('llava stub')
def tokenizer_image_token(*args, **kwargs):
    raise NotImplementedError('llava stub')
def get_model_name_from_path(*args, **kwargs):
    raise NotImplementedError('llava stub')
EOF
cat > "$SP/llava/constants.py" <<'EOF'
IMAGE_TOKEN_INDEX = -200
DEFAULT_IMAGE_TOKEN = '<image>'
DEFAULT_IM_START_TOKEN = '<im_start>'
DEFAULT_IM_END_TOKEN = '<im_end>'
IGNORE_INDEX = -100
EOF
cat > "$SP/llava/conversation.py" <<'EOF'
from enum import Enum, auto

class SeparatorStyle(Enum):
    SINGLE = auto()
    TWO = auto()
    PLAIN = auto()

conv_templates = {}
EOF

# 3) Patch t2v_metrics/__init__.py to guard the CLIPScore/ITMScore imports
#    (InternVideo2-CLIP / BLIP2-ITM backends) behind try/except — they're not
#    used by src/scoring.py (VQAScore only) and InternVideo2-CLIP alone pulls
#    in flash_attn (a compiled CUDA extension we don't want to build just to
#    satisfy an unused import chain).
INIT="$SP/t2v_metrics/__init__.py"
python - "$INIT" <<'PYEOF'
import re, sys
path = sys.argv[1]
src = open(path).read()
target = "from .clipscore import CLIPScore, list_all_clipscore_models\nfrom .itmscore import ITMScore, list_all_itmscore_models"
if target not in src:
    print("t2v_metrics/__init__.py already patched or has an unexpected shape — check manually.")
    sys.exit(0)
replacement = '''try:
    from .clipscore import CLIPScore, list_all_clipscore_models
except ImportError:
    CLIPScore = None
    def list_all_clipscore_models():
        return []

try:
    from .itmscore import ITMScore, list_all_itmscore_models
except ImportError:
    ITMScore = None
    def list_all_itmscore_models():
        return []'''
open(path, "w").write(src.replace(target, replacement))
print("patched", path)
PYEOF

echo "done. sanity check:"
python -c "import t2v_metrics; print(t2v_metrics.list_all_vqascore_models()[:3])"
