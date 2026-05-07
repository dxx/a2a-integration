import sys
from pathlib import Path

# 获取当前文件的上三级目录（即项目根目录），并加入搜索路径
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))
