from __future__ import annotations

import logging
from typing import Optional

import yaml
from pydantic import BaseModel, Field, ValidationError
from yaml import Loader, MappingNode, MarkedYAMLError, SafeLoader

from localstack.aws.api.lambda_ import Arn

LOG = logging.getLogger(__name__)


class LambdaDebugConfig(BaseModel):
    debug_port: Optional[int] = Field(None, alias="debug-port")
    timeout_disable: bool = Field(False, alias="timeout-disable")


class LambdaDebugModeConfig(BaseModel):
    # Bindings of Lambda function Arn and the respective debugging configuration.
    functions: dict[Arn, LambdaDebugConfig]


class LambdaDebugModeConfigException(Exception): ...


class PortAlreadyInUse(LambdaDebugModeConfigException):
    port_number: int

    def __init__(self, port_number: int):
        self.port_number = port_number

    def __str__(self):
        return f"PortAlreadyInUse: '{self.port_number}'"


class DuplicateLambdaDebugConfig(LambdaDebugModeConfigException):
    lambda_arn_debug_config_first: str
    lambda_arn_debug_config_second: str

    def __init__(self, lambda_arn_debug_config_first: str, lambda_arn_debug_config_second: str):
        self.lambda_arn_debug_config_first = lambda_arn_debug_config_first
        self.lambda_arn_debug_config_second = lambda_arn_debug_config_second

    def __str__(self):
        return (
            f"DuplicateLambdaDebugConfig: Lambda debug configuration in '{self.lambda_arn_debug_config_first}' "
            f"is redefined in '{self.lambda_arn_debug_config_second}'"
        )


class _LambdaDebugModeConfigValidationState:
    ports_used: set[int]

    def __init__(self):
        self.ports_used = set()


class _SafeLoaderWithDuplicateCheck(SafeLoader):
    def __init__(self, stream):
        super().__init__(stream)
        self.add_constructor(
            yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
            self._construct_mappings_with_duplicate_check,
        )

    @staticmethod
    def _construct_mappings_with_duplicate_check(loader: Loader, node: MappingNode, deep=False):
        # Constructs yaml bindings, whilst checking for duplicate mapping key definitions, raising a
        # MarkedYAMLError when one is found.
        mapping = dict()
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if key in mapping:
                # Create a MarkedYAMLError to indicate the duplicate key issue
                raise MarkedYAMLError(
                    context="while constructing a mapping",
                    context_mark=node.start_mark,
                    problem=f"found duplicate key: {key}",
                    problem_mark=key_node.start_mark,
                )
            value = loader.construct_object(value_node, deep=deep)
            mapping[key] = value
        return mapping


def from_yaml_string(yaml_string: str) -> Optional[LambdaDebugModeConfig]:
    try:
        data = yaml.load(yaml_string, _SafeLoaderWithDuplicateCheck)
    except yaml.YAMLError as yaml_error:
        LOG.error(
            f"Could not parse yaml lambda debug mode configuration file due to: {str(yaml_error)}"
        )
        data = None
    if not data:
        return None
    config = LambdaDebugModeConfig(**data)
    return config


def validate_lambda_debug_mode_config(config: LambdaDebugModeConfig) -> None:
    _validate_lambda_debug_mode_config(
        validation_state=_LambdaDebugModeConfigValidationState(), config=config
    )


def _validate_lambda_debug_mode_config(
    validation_state: _LambdaDebugModeConfigValidationState, config: LambdaDebugModeConfig
):
    config_functions = config.functions
    lambda_arns = list(config_functions.keys())
    for lambda_arn in lambda_arns:
        qualified_lambda_arn = _to_qualified_lambda_function_arn(lambda_arn)
        if lambda_arn != qualified_lambda_arn:
            if qualified_lambda_arn in config_functions:
                raise DuplicateLambdaDebugConfig(
                    lambda_arn_debug_config_first=lambda_arn,
                    lambda_arn_debug_config_second=qualified_lambda_arn,
                )
            config_functions[qualified_lambda_arn] = config_functions.pop(lambda_arn)

    for lambda_arn, lambda_debug_config in config_functions.items():
        _validate_lambda_debug_config(
            validation_state=validation_state, lambda_debug_config=lambda_debug_config
        )


def _to_qualified_lambda_function_arn(lambda_arn: Arn) -> Arn:
    # Returns the $LATEST qualified version of a structurally unqualified version of a lambda Arn iff this
    # if detected to be structurally unqualified. Otherwise, it returns the given string.
    if not lambda_arn:
        return lambda_arn
    lambda_arn_parts = lambda_arn.split(":")
    lambda_arn_parts_len = len(lambda_arn_parts)

    # The arn is qualified and with a non-empy qualifier.
    is_qualified = lambda_arn_parts_len == 8
    if is_qualified and lambda_arn_parts[-1]:
        return lambda_arn

    # The arn is not unqualified, but probably erroneous, pass the value upstream.
    is_unqualified = lambda_arn_parts_len == 7
    if not is_unqualified:
        return lambda_arn

    # Structure-wise, the arn is missing the qualifier.
    qualifier = "$LATEST"
    arn_tail = f":{qualifier}" if is_unqualified else qualifier
    qualified_lambda_arn = lambda_arn + arn_tail
    return qualified_lambda_arn


def _validate_lambda_debug_config(
    validation_state: _LambdaDebugModeConfigValidationState, lambda_debug_config: LambdaDebugConfig
) -> None:
    debug_port: Optional[int] = lambda_debug_config.debug_port
    if debug_port is None:
        return
    if debug_port in validation_state.ports_used:
        raise PortAlreadyInUse(port_number=debug_port)
    validation_state.ports_used.add(debug_port)


def load_lambda_debug_mode_config(yaml_string: str) -> Optional[LambdaDebugModeConfig]:
    # Attempt to parse the yaml string.
    try:
        yaml_data = yaml.load(yaml_string, _SafeLoaderWithDuplicateCheck)
    except yaml.YAMLError as yaml_error:
        LOG.error(
            f"Could not parse yaml lambda debug mode configuration file due to: {str(yaml_error)}"
        )
        yaml_data = None
    if not yaml_data:
        return None

    # Attempt to build the LambdaDebugModeConfig object from the yaml object.
    try:
        config = LambdaDebugModeConfig(**yaml_data)
    except ValidationError as validation_error:
        validation_errors = validation_error.errors() or list()
        error_messages = [
            f"When parsing '{err.get('loc', '')}': {err.get('msg', str(err))}"
            for err in validation_errors
        ]
        LOG.error(
            f"Unable to parse lambda debug mode configuration file due to errors: {error_messages}"
        )
        return None

    # Attempt to validate the configuration.
    try:
        validate_lambda_debug_mode_config(config)
    except LambdaDebugModeConfigException as lambda_debug_mode_error:
        LOG.error(f"Invalid lambda debug mode configuration due to: {lambda_debug_mode_error}")
        config = None

    return config