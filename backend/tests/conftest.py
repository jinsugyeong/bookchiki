"""pytest 공통 픽스처."""
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import numpy as np
import pytest
