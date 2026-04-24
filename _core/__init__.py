"""
TaskWatcher 核心模块
"""
try:
    from .github_client import GitHubAPIClient
    _GITHUB_CLIENT_AVAILABLE = True
except ImportError as e:
    print(f"[WARNING] github_client import failed: {e}")
    print("[WARNING] Please ensure aiohttp is installed: pip install aiohttp")
    _GITHUB_CLIENT_AVAILABLE = False
    GitHubAPIClient = None

try:
    from .task_parser import TaskBookParser
    _TASK_PARSER_AVAILABLE = True
except ImportError as e:
    print(f"[WARNING] task_parser import failed: {e}")
    _TASK_PARSER_AVAILABLE = False
    TaskBookParser = None

try:
    from .task_matcher import TaskMatcher
    _TASK_MATCHER_AVAILABLE = True
except ImportError as e:
    print(f"[WARNING] task_matcher import failed: {e}")
    _TASK_MATCHER_AVAILABLE = False
    TaskMatcher = None

try:
    from .ai_analyzer import AIAnalyzer
    _AI_ANALYZER_AVAILABLE = True
except ImportError as e:
    print(f"[WARNING] ai_analyzer import failed: {e}")
    _AI_ANALYZER_AVAILABLE = False
    AIAnalyzer = None

try:
    from .utils import FileUtils, DataFormatter, ConfigUtils, Validator
    _UTILS_AVAILABLE = True
except ImportError as e:
    print(f"[WARNING] utils import failed: {e}")
    _UTILS_AVAILABLE = False
    FileUtils = DataFormatter = ConfigUtils = Validator = None

# 只导出可用的模块
__all__ = []

if _GITHUB_CLIENT_AVAILABLE and GitHubAPIClient is not None:
    __all__.append('GitHubAPIClient')

if _TASK_PARSER_AVAILABLE and TaskBookParser is not None:
    __all__.append('TaskBookParser')

if _TASK_MATCHER_AVAILABLE and TaskMatcher is not None:
    __all__.append('TaskMatcher')

if _AI_ANALYZER_AVAILABLE and AIAnalyzer is not None:
    __all__.append('AIAnalyzer')

if _UTILS_AVAILABLE and FileUtils is not None:
    __all__.append('FileUtils')

if _UTILS_AVAILABLE and DataFormatter is not None:
    __all__.append('DataFormatter')

if _UTILS_AVAILABLE and ConfigUtils is not None:
    __all__.append('ConfigUtils')

if _UTILS_AVAILABLE and Validator is not None:
    __all__.append('Validator')