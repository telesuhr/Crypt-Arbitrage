#!/usr/bin/env python3
"""
データベーススキーマの更新
lastカラムを追加
"""

import sys
from pathlib import Path
from sqlalchemy import text

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database.connection import db

def update_schema():
    """スキーマを更新"""
    with db.engine.connect() as conn:
        # lastカラムが存在するかチェック
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'price_ticks' 
            AND column_name = 'last'
        """))
        
        if not result.fetchone():
            print("Adding 'last' column to price_ticks table...")
            conn.execute(text("""
                ALTER TABLE price_ticks 
                ADD COLUMN IF NOT EXISTS last DECIMAL(20, 8)
            """))
            conn.commit()
            print("✅ Column added successfully!")
        else:
            print("✅ 'last' column already exists")

if __name__ == "__main__":
    update_schema()