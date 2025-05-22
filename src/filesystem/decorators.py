from functools import wraps
from inspect import Parameter, Signature, signature
from typing import (
    Any,
    Awaitable,
    Callable,
    List,
    Optional,
    ParamSpec,
    Type,
    TypeVar,
)

from pydantic import BaseModel, ValidationError
from pydantic_core import PydanticUndefined

# --- Define TypeVars for precise generic typing ---
R = TypeVar("R")  # Represents the actual (awaited) data type returned by the function
P_Original = ParamSpec("P_Original")  # Represents the original parameters of func


def flat_args(
    model_cls: Type[BaseModel],
) -> Callable[  # Type of the decorator factory's return (i.e., type of 'decorator' function)
    [Callable[P_Original, Awaitable[R]]],  # Argument to 'decorator' (this is 'func')
    Callable[..., Awaitable[R]],  # Return of 'decorator' (the 'wrapped_func')
]:
    """Decorator to flatten a Pydantic model's fields into function parameters."""

    def decorator(
        func: Callable[P_Original, Awaitable[R]],
    ) -> Callable[..., Awaitable[R]]:  # Decorator takes func, returns new callable
        field_details_for_signature: List[tuple[str, Any, Any]] = []
        ordered_field_names: List[str] = []

        is_pydantic_v2 = hasattr(model_cls, "model_fields")
        current_sig = signature(func)  # Original function's signature

        if is_pydantic_v2:
            for name, field_info_v2 in model_cls.model_fields.items():
                ordered_field_names.append(name)
                param_default = Parameter.empty
                if not field_info_v2.is_required():
                    if field_info_v2.default is not PydanticUndefined:
                        param_default = field_info_v2.default
                field_details_for_signature.append(
                    (name, param_default, field_info_v2.annotation)
                )
        else:  # Pydantic v1
            for name, model_field_v1 in model_cls.__fields__.items():  # type: ignore[attr-defined]
                ordered_field_names.append(name)
                param_default = (
                    Parameter.empty
                    if model_field_v1.required
                    else model_field_v1.default
                )
                annotation_val = getattr(
                    model_field_v1, "annotation", getattr(model_field_v1, "type_", Any)
                )
                field_details_for_signature.append(
                    (name, param_default, annotation_val)
                )

        new_signature_params: List[Parameter] = []
        for name, p_default, p_anno in field_details_for_signature:
            new_signature_params.append(
                Parameter(
                    name=name,
                    kind=Parameter.POSITIONAL_OR_KEYWORD,
                    default=p_default,
                    annotation=p_anno if p_anno is not None else Any,
                )
            )

        orig_params_list = list(current_sig.parameters.values())
        is_method = bool(orig_params_list and orig_params_list[0].name == "self")

        final_signature_params: List[Parameter] = []
        if is_method:
            final_signature_params.append(orig_params_list[0])
        final_signature_params.extend(new_signature_params)

        @wraps(func)
        async def async_wrapper(*call_args_raw: Any, **kwargs: Any) -> R:
            self_arg: Optional[Any] = None
            if is_method:
                if not call_args_raw:
                    raise TypeError(f"Method {func.__name__} needs a 'self' argument.")
                self_arg = call_args_raw[0]

            # --- Handle Passthrough Mode ---
            if is_method:
                if len(call_args_raw) > 1 and isinstance(call_args_raw[1], model_cls):
                    if len(call_args_raw) > 2:
                        raise TypeError(
                            f"{func.__name__} passthrough called with too many positional arguments after model."
                        )
                    model_instance_to_pass = call_args_raw[1]
                    # Providing specific type ignores for [arg-type] if they appear.
                    # MyPy struggles to match (Any, BaseModel, **kwargs) to P_Original.
                    res_passthrough_meth: R = await func(
                        self_arg,  # type: ignore[arg-type]
                        model_instance_to_pass,  # type: ignore[arg-type]
                        **kwargs,
                    )
                    return res_passthrough_meth
            else:  # Not a method
                if len(call_args_raw) == 1 and isinstance(call_args_raw[0], model_cls):
                    if len(call_args_raw) > 1:
                        raise TypeError(
                            f"{func.__name__} passthrough called with too many positional arguments after model."
                        )
                    model_instance_to_pass = call_args_raw[0]
                    res_passthrough_func: R = await func(
                        model_instance_to_pass,  # type: ignore[arg-type]
                        **kwargs,
                    )
                    return res_passthrough_func

            # --- Model Reconstruction ---
            model_constructor_kwargs: dict[str, Any] = {}
            model_field_positional_args: tuple[Any, ...]
            if is_method:
                model_field_positional_args = call_args_raw[1:]
            else:
                model_field_positional_args = call_args_raw

            for i, arg_val in enumerate(model_field_positional_args):
                if i < len(ordered_field_names):
                    field_name = ordered_field_names[i]
                    model_constructor_kwargs[field_name] = arg_val
                else:
                    break

            for field_name_key in ordered_field_names:
                if field_name_key in kwargs:
                    if field_name_key in model_constructor_kwargs:
                        raise TypeError(
                            f"{func.__name__}() got multiple values for argument '{field_name_key}'"
                        )
                    model_constructor_kwargs[field_name_key] = kwargs.pop(
                        field_name_key
                    )

            try:
                model_instance_to_pass = model_cls(**model_constructor_kwargs)
            except ValidationError as e:
                raise e

            final_func_args_tuple: tuple[Any, ...]
            if is_method:
                final_func_args_tuple = (self_arg, model_instance_to_pass)
            else:
                final_func_args_tuple = (model_instance_to_pass,)

            res_reconstruct: R = await func(*final_func_args_tuple, **kwargs)
            return res_reconstruct

        # Assign to a variable first to easily manage its type for attribute assignment
        # async_wrapper is `async def ... -> R`, so its type is `Callable[..., Awaitable[R]]`
        # which matches the return type annotation of `decorator`.
        the_actual_wrapper_function = async_wrapper

        # Set runtime introspection attributes
        final_annotations = {p.name: p.annotation for p in final_signature_params}
        final_annotations["return"] = current_sig.return_annotation  # This is R

        # Functions are objects and allow attribute assignment.
        # MyPy might be overly cautious with complex generic callables.
        # If attr-defined persists, casting `the_actual_wrapper_function` to `Any`
        # before these assignments is a workaround, or using setattr().
        try:
            setattr(the_actual_wrapper_function, "__annotations__", final_annotations)
            setattr(
                the_actual_wrapper_function,
                "__signature__",
                Signature(
                    parameters=final_signature_params,
                    return_annotation=current_sig.return_annotation,  # R
                ),
            )
        except Exception as e:
            print(
                f"Warning: Could not set __signature__ or __annotations__ for {func.__name__} due to: {e}"
            )
            pass

        return the_actual_wrapper_function

    return decorator
