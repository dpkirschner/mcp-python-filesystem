import sys
from .filesystem import FilesystemContext

# For backward compatibility
context = sys.modules[__name__]

__all__ = ['FilesystemContext', 'context']
