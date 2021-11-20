from collections import defaultdict, deque
from random import choice
from typing import Any, Callable, Dict, Optional, cast

from pydantic.fields import (
    SHAPE_DEFAULTDICT,
    SHAPE_DEQUE,
    SHAPE_DICT,
    SHAPE_FROZENSET,
    SHAPE_ITERABLE,
    SHAPE_LIST,
    SHAPE_MAPPING,
    SHAPE_SEQUENCE,
    SHAPE_SET,
    SHAPE_TUPLE,
    SHAPE_TUPLE_ELLIPSIS,
    ModelField,
)

from pydantic_factories.exceptions import ParameterError
from pydantic_factories.value_generators.primitives import create_random_string

type_mapping = {
    "Dict": dict,
    "Sequence": list,
    "List": list,
    "Set": set,
    "Deque": deque,
    "Mapping": dict,
    "Tuple": tuple,
    "DefaultDict": defaultdict,
    "FrozenSet": frozenset,
    "Iterable": list,
}

shape_mapping = {
    SHAPE_LIST: list,
    SHAPE_SET: set,
    SHAPE_MAPPING: dict,
    SHAPE_TUPLE: tuple,
    SHAPE_TUPLE_ELLIPSIS: tuple,
    SHAPE_SEQUENCE: list,
    SHAPE_FROZENSET: frozenset,
    SHAPE_ITERABLE: list,
    SHAPE_DEQUE: deque,
    SHAPE_DICT: dict,
    SHAPE_DEFAULTDICT: defaultdict,
}


def is_union(model_field: ModelField) -> bool:
    """Determines whether the given model_field is type Union"""
    return repr(model_field.outer_type_).split("[")[0] == "typing.Union"


def is_any(model_field: ModelField) -> bool:
    """Determines whether the given model_field is type Any"""
    return model_field.type_ is Any or (
        hasattr(model_field.outer_type_, "_name") and "Any" in getattr(model_field.outer_type_, "_name")
    )


def handle_container_type(model_field: ModelField, container_type: Callable, providers: Dict[Any, Callable]):
    """Handles generation of container types, e.g. dict, list etc. recursively"""
    is_frozen_set = False
    if container_type == frozenset:
        container = set()
        is_frozen_set = True
    else:
        container = container_type()
    value = None
    if model_field.sub_fields:
        value = handle_complex_type(model_field=choice(model_field.sub_fields), providers=providers)
    if isinstance(container, (dict, defaultdict)):
        container[handle_complex_type(model_field=model_field.key_field, providers=providers)] = value
    elif isinstance(container, (list, deque)):
        container.append(value)
    else:
        container.add(value)
        if is_frozen_set:
            container = cast(set, frozenset(*container))
    return container


def handle_complex_type(model_field: ModelField, providers: Dict[Any, Callable]) -> Any:
    """Recursive type generation based on typing info stored in the graphic like structure of pydantic model_fields"""
    container_type: Optional[Callable] = shape_mapping.get(model_field.shape)
    if container_type:
        if container_type != tuple:
            return handle_container_type(model_field=model_field, container_type=container_type, providers=providers)
        return tuple(
            handle_complex_type(model_field=sub_field, providers=providers)
            for sub_field in (model_field.sub_fields or [])
        )
    if is_union(model_field=model_field) and model_field.sub_fields:
        return handle_complex_type(model_field=choice(model_field.sub_fields), providers=providers)
    if is_any(model_field=model_field):
        return create_random_string(min_length=1, max_length=10)
    if model_field.type_ in providers:
        return providers[model_field.type_]()
    raise ParameterError(
        f"Unsupported type: {repr(model_field.type_)}"
        f"\n\nEither extend the providers map or add a factory function for this model field"
    )