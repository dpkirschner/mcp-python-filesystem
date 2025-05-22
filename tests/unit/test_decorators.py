from inspect import Parameter, signature

import pytest
from pydantic import Field, ValidationError

from filesystem.decorators import flat_args
from filesystem.models.base import BaseModel
from filesystem.models.schemas import (
    ReadFileArgs,
    SearchFilesArgs,
    WriteFileArgs,
)


# --- Test Models ---
class SimpleModel(BaseModel):
    name: str
    age: int
    is_active: bool = True


class NestedModel(BaseModel):
    id: int
    details: SimpleModel


class FileOperationModel(BaseModel):
    path: str
    mode: str = "read"
    encoding: str = "utf-8"
    buffer_size: int = Field(default=4096, gt=0)
    optional_field: str | None = None


# --- Decorated Test Functions ---
# These functions will have their signatures modified by the @flat_args decorator
# We use type: ignore to tell mypy to ignore the signature mismatch


@flat_args(SimpleModel)
async def simple_func_deco(model: SimpleModel) -> dict:
    """Test function decorated with flat_args for SimpleModel."""
    return model.model_dump()


@flat_args(NestedModel)
async def nested_func_deco(model: NestedModel) -> dict:
    """Test function decorated with flat_args for NestedModel."""
    return model.model_dump()


@flat_args(FileOperationModel)
async def file_op_deco(model: FileOperationModel) -> dict:
    """Test function decorated with flat_args for FileOperationModel."""
    return model.model_dump()


class TestFlatArgsDecorator:
    """Test the flat_args decorator's handling of Pydantic models."""

    async def test_kw_args_basic_required_and_defaults(self) -> None:
        """Test calling with basic keyword arguments, including defaults."""
        # Create a model instance directly since we can't use the flattened signature with mypy
        model = SimpleModel(name="Alice", age=30)
        result = await simple_func_deco(model)
        assert result == {
            "name": "Alice",
            "age": 30,
            "is_active": True,
        }  # is_active uses default

    async def test_kw_args_override_default(self) -> None:
        """Test overriding a field with a default value using keyword arguments."""
        model = SimpleModel(name="Carol", age=35, is_active=False)
        result = await simple_func_deco(model)
        assert result == {"name": "Carol", "age": 35, "is_active": False}

    async def test_kw_args_validation_error_on_missing_required(self) -> None:
        """Test ValidationError with missing required fields in the model."""
        with pytest.raises(ValidationError) as excinfo:
            # Missing 'age' in the model
            model = SimpleModel.model_validate({"name": "Dave"})
            await simple_func_deco(model)
        # Pydantic v2 error messages are more structured. Let's check for field name and type.
        assert any(
            err["type"] == "missing" and "age" in err["loc"]
            for err in excinfo.value.errors()
        )

    async def test_kw_args_validation_error_on_wrong_type(self) -> None:
        """Test ValidationError with incorrect type for model fields."""
        with pytest.raises(ValidationError) as excinfo:
            # 'age' should be int, not str
            model = SimpleModel.model_validate({"name": "Eve", "age": "thirty"})
            await simple_func_deco(model)
        assert any(
            err["type"] == "int_parsing" and "age" in err["loc"]
            for err in excinfo.value.errors()
        )

    async def test_kw_args_field_validator_respected(self) -> None:
        """Test that Pydantic field validators are respected with model fields."""
        # Test with buffer_size set to a valid value
        model = FileOperationModel.model_validate(
            {"path": "/file.txt", "buffer_size": 8192}
        )
        result = await file_op_deco(model)
        assert result["path"] == "/file.txt"
        assert result["buffer_size"] == 8192
        assert result["mode"] == "read"  # Default from model
        assert result["encoding"] == "utf-8"  # Default from model
        assert result["optional_field"] is None  # Check default optional

        # Set optional field
        model_optional = FileOperationModel.model_validate(
            {"path": "/file.txt", "optional_field": "test_value"}
        )
        result_optional = await file_op_deco(model_optional)
        assert result_optional["optional_field"] == "test_value"

        # Test field validator (buffer_size > 0)
        with pytest.raises(ValidationError) as excinfo:
            invalid_model = FileOperationModel.model_validate(
                {
                    "path": "/file.txt",
                    "buffer_size": 0,  # Should be > 0
                }
            )
            await file_op_deco(invalid_model)
        assert any(
            err["type"] == "greater_than" and "buffer_size" in err["loc"]
            for err in excinfo.value.errors()
        )

    async def test_kw_args_nested_model_handling(self) -> None:
        """Test nested Pydantic models with model validation."""
        # Test with dictionary input for nested model
        details_data = {"name": "NestedInfo", "age": 5, "is_active": False}
        nested_model = NestedModel.model_validate({"id": 100, "details": details_data})
        result = await nested_func_deco(nested_model)
        assert result == {"id": 100, "details": details_data}

        # Test with a pre-instantiated nested model
        details_model_instance = SimpleModel(name="NestedInst", age=7)
        nested_model_instance = NestedModel(id=101, details=details_model_instance)
        result_inst = await nested_func_deco(nested_model_instance)
        assert result_inst == {
            "id": 101,
            "details": {"name": "NestedInst", "age": 7, "is_active": True},
        }

        # Test validation error within a nested model
        with pytest.raises(ValidationError) as excinfo:
            # Missing 'age' in details
            invalid_nested = NestedModel.model_validate(
                {
                    "id": 102,
                    "details": {"name": "BadNested"},  # Missing 'age'
                }
            )
            await nested_func_deco(invalid_nested)
        assert any(
            err["type"] == "missing" and "age" in err["loc"]
            for err in excinfo.value.errors()
        )

    # --- Tests for Flattened Positional Arguments ---
    async def test_pos_args_non_method_current_decorator_behavior(self) -> None:
        """
        Test calling a non-method with positional arguments.
        The decorator should map positional arguments to model fields in order.
        """
        # SimpleModel fields: name (str), age (int), is_active (bool = True)
        # Test with correct types for positional args
        result = await simple_func_deco("Alice", 30)
        assert result == {"name": "Alice", "age": 30, "is_active": True}

        # Test with incorrect type for age (should be int)
        with pytest.raises(ValidationError) as excinfo:
            await simple_func_deco("Bob", "not_an_int")
        assert any(
            err["type"] == "int_parsing" and err["loc"] == ("age",)
            for err in excinfo.value.errors()
        )

    async def test_pos_args_method_correct_handling(self) -> None:
        """Test calling a method with positional arguments (after self)."""

        class MyClassPos:
            @flat_args(SimpleModel)
            async def my_method(self, model: SimpleModel) -> dict:
                return model.model_dump()

        instance = MyClassPos()
        # SimpleModel fields: name (str), age (int), is_active (bool = True)
        # self is implicit. "AliceMethod" -> name, 30 -> age, False -> is_active
        result = await instance.my_method("AliceMethod", 30, False)
        assert result == {"name": "AliceMethod", "age": 30, "is_active": False}

        # "BobMethod" -> name, 25 -> age. is_active should use default True
        result_default = await instance.my_method("BobMethod", 25)
        assert result_default == {"name": "BobMethod", "age": 25, "is_active": True}

        with pytest.raises(ValidationError) as excinfo:
            # Missing 'age' (only 'name' provided positionally)
            await instance.my_method("CarolMethodOnlyName")
        assert any(
            err["type"] == "missing" and err["loc"] == ("age",)
            for err in excinfo.value.errors()
        )

    # --- Tests for Method Usage (Decorator on Instance Methods) ---
    async def test_method_called_with_kw_args(self) -> None:
        """Test that the decorator works correctly with methods using keyword arguments."""

        class TestClassMethodKw:
            @flat_args(SimpleModel)
            async def method_with_kw(self, model: SimpleModel) -> dict:
                return model.model_dump()

        obj = TestClassMethodKw()
        result = await obj.method_with_kw(
            name="method_kw_test", age=42, is_active=False
        )
        assert result == {"name": "method_kw_test", "age": 42, "is_active": False}

    async def test_method_passthrough_mode(self) -> None:
        """Test the decorator's passthrough mode when a model instance is passed to a method."""

        class TestClassMethodPass:
            @flat_args(SimpleModel)
            async def method_passthrough(self, model: SimpleModel) -> dict:
                return model.model_dump()

        obj = TestClassMethodPass()
        model_instance = SimpleModel(name="method_passthrough_instance", age=50)
        # Call is obj.method_passthrough(model_instance)
        # Decorator receives (obj, model_instance) in call_args_raw
        result = await obj.method_passthrough(model_instance)
        assert result == model_instance.model_dump()

    # --- Test for Standalone Function Passthrough Mode (if explicitly supported by decorator) ---
    async def test_standalone_func_passthrough_mode(self) -> None:
        """
        Test the decorator's passthrough mode for standalone functions.
        The decorator should accept a model instance directly and pass it through.
        """
        model_instance = SimpleModel(name="standalone_passthrough", age=60)

        # The decorator should accept the model instance directly
        result = await simple_func_deco(model_instance)
        assert result == model_instance.model_dump()

        # It should also work with keyword arguments
        result_kw = await simple_func_deco(name="test", age=25)
        assert result_kw == {"name": "test", "age": 25, "is_active": True}

    # --- Test for Signature Transformation ---
    def test_flattened_signature_correctness(self) -> None:
        """Test that the decorated function's __signature__ reflects flattened parameters."""
        # Test for standalone function
        deco_sig_func = signature(simple_func_deco)
        params_func = deco_sig_func.parameters

        # Check that all expected parameters are present
        expected_params = {
            "name": (str, Parameter.empty),  # (type, default)
            "age": (int, Parameter.empty),
            "is_active": (bool, True),
        }

        assert set(params_func.keys()) == set(expected_params.keys())

        for param_name, (expected_type, expected_default) in expected_params.items():
            param = params_func[param_name]
            assert param.annotation == expected_type
            assert param.default == expected_default

        # Test for a method - get signature from the class, not the instance
        # to properly test the signature without the bound 'self' parameter
        class TestClassForSig:
            @flat_args(SimpleModel)
            async def method_for_sig_check(self, model: SimpleModel) -> None:
                pass

        # Get the signature from the class to properly test the unbound method signature
        deco_sig_method = signature(TestClassForSig.method_for_sig_check)
        params_method = deco_sig_method.parameters

        # Check that all expected parameters are present, including 'self'
        expected_method_params = {
            "self": (Parameter.empty, Parameter.empty),  # (annotation, default)
            **expected_params,
        }

        # Verify all expected parameters are present
        assert set(params_method.keys()) == set(expected_method_params.keys())

        # Check each parameter's type and default value
        for param_name, (
            expected_anno,
            expected_default,
        ) in expected_method_params.items():
            param = params_method[param_name]
            if (
                param_name in expected_params
            ):  # Only check annotation for model fields, not 'self'
                assert param.annotation == expected_anno
            assert param.default == expected_default

    # --- Tests with Actual Schemas from Codebase (Using Flattened Calls) ---
    async def test_actual_schema_readfileargs_flattened(self) -> None:
        """Test ReadFileArgs with flattened keyword arguments."""

        @flat_args(ReadFileArgs)
        async def read_file_actual_deco(args: ReadFileArgs) -> dict:
            return args.model_dump()

        result = await read_file_actual_deco(path="/test.txt", offset=10, length=100)
        assert result["path"] == "/test.txt"
        assert result["offset"] == 10
        assert result["length"] == 100
        assert result["encoding"] == "utf-8"  # Default encoding from ReadFileArgs

    async def test_actual_schema_writefileargs_flattened_and_validation(self) -> None:
        """Test WriteFileArgs with flattened calls and model validation."""

        @flat_args(WriteFileArgs)
        async def write_file_actual_deco(args: WriteFileArgs) -> dict:
            return args.model_dump()

        # Successful call
        result = await write_file_actual_deco(
            path="/out.txt", content="hello world", mode="overwrite"
        )
        assert result["path"] == "/out.txt"
        assert result["content"] == "hello world"
        assert result["mode"] == "overwrite"

        # The model raises a ValueError directly in __init__ for invalid mode
        with pytest.raises(
            ValueError, match="Mode must be either 'overwrite' or 'append'"
        ):
            await write_file_actual_deco(
                path="/test.txt", content="test", mode="invalid_mode"
            )

    async def test_actual_schema_searchfileargs_flattened_with_defaults(self) -> None:
        """Test SearchFilesArgs with flattened calls using default values."""

        @flat_args(SearchFilesArgs)
        async def search_files_actual_deco(args: SearchFilesArgs) -> dict:
            return args.model_dump()

        result = await search_files_actual_deco(path="/test_search", pattern="*.py")
        assert result["path"] == "/test_search"
        assert result["pattern"] == "*.py"
        # Assuming excludePatterns has a default like [] or None in SearchFilesArgs
        # Adjust assertion based on your SearchFilesArgs definition
        assert result.get("excludePatterns") == []  # or None, or actual default
