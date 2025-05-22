from functools import wraps
from inspect import Parameter, signature
from typing import Any, Callable, Type, TypeVar, cast

from pydantic import BaseModel

T = TypeVar("T", bound=Callable[..., Any])


def flat_args(model_cls: Type[BaseModel]) -> Callable[[T], T]:
    """Decorator to flatten a Pydantic model's fields into function parameters.

    This allows tool functions to be called with individual parameters that will be
    automatically converted to the specified model. The function will receive a single
    argument that is an instance of the model.

    Args:
        model_cls: The Pydantic model class to use for parameter validation.

    Returns:
        A decorator that transforms the function to accept flattened parameters.
    """

    def decorator(func: T) -> T:
        # Get the model's field information
        model_sig = signature(model_cls.__init__)
        model_params = {
            k: v
            for k, v in model_sig.parameters.items()
            if k != "self"
            and v.kind in (Parameter.POSITIONAL_OR_KEYWORD, Parameter.KEYWORD_ONLY)
        }

        # Build a new function signature with the model's fields as parameters
        new_params = list(model_params.values())

        # Create the wrapper function
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Handle instance methods (self is the first arg)
            if (
                args
                and hasattr(args[0], "__class__")
                and not isinstance(args[0], model_cls)
            ):
                self_arg = args[0]
                other_args = args[1:]

                # If the next arg is already an instance of the model, use it
                if other_args and isinstance(other_args[0], model_cls):
                    return await func(self_arg, other_args[0])
                # Otherwise, create model from kwargs
                model = model_cls(**kwargs)
                return await func(self_arg, model)
            # Handle standalone functions or direct model instance
            elif args and isinstance(args[0], model_cls):
                return await func(*args, **kwargs)
            # Create model from kwargs for standalone functions
            else:
                model = model_cls(**kwargs)
                return await func(model)

        # Update the signature to show the flattened parameters
        wrapper.__signature__ = signature(func).replace(parameters=new_params)  # type: ignore[attr-defined]
        return cast(T, wrapper)

    return decorator
