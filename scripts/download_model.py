from huggingface_hub import snapshot_download
import os

REPO_ID = "pollitoconpapass/QnIA-translation-model"
OUT_DIR = os.path.join(os.getcwd(), "model", "qnia")
os.makedirs(OUT_DIR, exist_ok=True)

print("Downloading model snapshot to", OUT_DIR)
# snapshot_download descarga todo el repo del modelo (shards incluidos) y lo pone en cache
snapshot_download(repo_id=REPO_ID, local_dir=OUT_DIR, local_dir_use_symlinks=False)
print("Download finished.")
