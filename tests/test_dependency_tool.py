from app.tools.dependency_tool import (
    install_spec_for_package,
    package_for_module,
    package_from_missing_dependency,
)


def test_package_from_missing_dependency_parses_module_not_found():
    package = package_from_missing_dependency(
        "ModuleNotFoundError: No module named 'gradio.routes'",
        "",
    )

    assert package == "gradio"


def test_package_for_module_uses_common_package_renames():
    assert package_for_module("cv2") == "opencv-python-headless"
    assert package_for_module("PIL.Image") == "pillow"
    assert package_for_module("sklearn.metrics") == "scikit-learn"


def test_package_from_missing_distribution():
    package = package_from_missing_dependency(
        "importlib.metadata.PackageNotFoundError: No package metadata was found for open-clip-torch",
        "",
    )

    assert package == "open-clip-torch"


def test_install_spec_pins_gradio_to_compatible_version():
    assert install_spec_for_package("gradio") == "gradio==3.16.2"
    assert install_spec_for_package("numpy") == "numpy"
