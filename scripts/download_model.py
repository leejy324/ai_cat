"""
预下载 embedding 模型到本地目录，供 Docker 构建时 COPY 进镜像。

使用方法（需要先开启 VPN）：
    python scripts/download_model.py

模型会保存到项目根目录的 models/bge-large-zh-v1.5/ 下。
之后 docker compose build 时不再需要联网下载。
"""

import os
import subprocess
import sys

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_NAME = "BAAI/bge-large-zh-v1.5"
SAVE_DIR = os.path.join(PROJECT_ROOT, "models", "bge-large-zh-v1.5")


def ensure_dependencies():
    """检查并自动安装所需依赖"""
    try:
        import sentence_transformers  # noqa: F401
        return
    except ImportError:
        pass

    print("检测到缺少 sentence-transformers，正在自动安装...")
    print("(包含 PyTorch 等大型依赖，首次安装可能需要几分钟)\n")
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "sentence-transformers"
        ])
        print("\n依赖安装完成！\n")
    except subprocess.CalledProcessError:
        print("\n错误：依赖安装失败，请手动运行以下命令：")
        print(f"  {sys.executable} -m pip install sentence-transformers")
        sys.exit(1)


def main():
    print(f"即将下载模型 {MODEL_NAME} ...")
    print(f"保存位置: {SAVE_DIR}\n")

    ensure_dependencies()

    from sentence_transformers import SentenceTransformer

    print("正在从 HuggingFace 下载模型（约 1.3GB）...")
    print("如果下载失败，请确认 VPN 已开启。\n")

    model = SentenceTransformer(MODEL_NAME)
    model.save(SAVE_DIR)

    # 验证关键文件存在
    safetensors = os.path.join(SAVE_DIR, "model.safetensors")
    if not os.path.exists(safetensors):
        print(f"\n⚠️ 警告：模型文件 {safetensors} 不存在，下载可能不完整")
        sys.exit(1)

    print(f"\n✅ 模型已成功保存到 {SAVE_DIR}")
    print("现在可以运行 docker compose up -d --build 构建镜像了")


if __name__ == "__main__":
    main()
