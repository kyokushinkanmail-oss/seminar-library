#!/usr/bin/env bash
# Render.com ビルドスクリプト
set -o errexit

pip install -r requirements.txt

# データディレクトリ作成
mkdir -p data

# 初期データ投入（初回のみ）
python3 seed.py
