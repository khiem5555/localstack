import pytest

from localstack.utils.lambda_debug_mode.lambda_debug_mode_config import (
    load_lambda_debug_mode_config,
)

DEBUG_CONFIG_EMPTY = ""

DEBUG_CONFIG_NULL_FUNCTIONS = """
functions:
    null
"""

DEBUG_CONFIG_NULL_FUNCTION_CONFIG = """
functions:
  arn:aws:lambda:eu-central-1:000000000000:function:functionname:$LATEST:
    null
"""

DEBUG_CONFIG_NULL_DEBUG_PORT = """
functions:
  arn:aws:lambda:eu-central-1:000000000000:function:functionname:
    debug-port: null
"""

DEBUG_CONFIG_NULL_TIMEOUT_DISABLE = """
functions:
  arn:aws:lambda:eu-central-1:000000000000:function:functionname:
    debug-port: null
"""

DEBUG_CONFIG_DUPLICATE_DEBUG_PORT = """
functions:
  arn:aws:lambda:eu-central-1:000000000000:function:functionname1:
    debug-port: 19891
  arn:aws:lambda:eu-central-1:000000000000:function:functionname2:
    debug-port: 19891
"""

DEBUG_CONFIG_DUPLICATE_ARN = """
functions:
  arn:aws:lambda:eu-central-1:000000000000:function:functionname:
    debug-port: 19891
  arn:aws:lambda:eu-central-1:000000000000:function:functionname:
    debug-port: 19892
"""

DEBUG_CONFIG_DUPLICATE_IMPLICIT_ARN = """
functions:
  arn:aws:lambda:eu-central-1:000000000000:function:functionname:
    debug-port: 19891
  arn:aws:lambda:eu-central-1:000000000000:function:functionname:$LATEST:
    debug-port: 19892
"""

DEBUG_CONFIG_BASE = """
functions:
  arn:aws:lambda:eu-central-1:000000000000:function:functionname:$LATEST:
    debug-port: 19891
"""

DEBUG_CONFIG_BASE_UNQUALIFIED = """
functions:
  arn:aws:lambda:eu-central-1:000000000000:function:functionname:
    debug-port: 19891
"""


@pytest.mark.parametrize(
    "yaml_config",
    [
        DEBUG_CONFIG_EMPTY,
        DEBUG_CONFIG_NULL_FUNCTIONS,
        DEBUG_CONFIG_NULL_FUNCTION_CONFIG,
        DEBUG_CONFIG_DUPLICATE_DEBUG_PORT,
        DEBUG_CONFIG_DUPLICATE_ARN,
        DEBUG_CONFIG_DUPLICATE_IMPLICIT_ARN,
    ],
    ids=[
        "empty",
        "null_functions",
        "null_function_config",
        "duplicate_debug_port",
        "deplicate_arn",
        "duplicate_implicit_arn",
    ],
)
def test_debug_config_invalid(yaml_config: str):
    assert load_lambda_debug_mode_config(yaml_config) is None


def test_debug_config_null_debug_port():
    config = load_lambda_debug_mode_config(DEBUG_CONFIG_NULL_DEBUG_PORT)
    assert list(config.lambdas.values())[0].debug_port is None


def test_debug_config_null_timeout_disable():
    config = load_lambda_debug_mode_config(DEBUG_CONFIG_NULL_TIMEOUT_DISABLE)
    assert list(config.lambdas.values())[0].timeout_disable is False


@pytest.mark.parametrize(
    "yaml_config",
    [
        DEBUG_CONFIG_BASE,
        DEBUG_CONFIG_BASE_UNQUALIFIED,
    ],
    ids=[
        "base",
        "base_unqualified",
    ],
)
def test_debug_config_base(yaml_config):
    config = load_lambda_debug_mode_config(yaml_config)
    assert len(config.lambdas) == 1
    assert (
        "arn:aws:lambda:eu-central-1:000000000000:function:functionname:$LATEST" in config.lambdas
    )
    assert list(config.lambdas.values())[0].debug_port == 19891
    assert list(config.lambdas.values())[0].timeout_disable is False