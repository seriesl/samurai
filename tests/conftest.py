import re
import os
import pytest
import h5py
from functools import wraps
import shutil
import tempfile
import warnings


def pytest_addoption(parser):
    group = parser.getgroup("h5 file comparison")
    group.addoption(
        "--h5diff",
        action="store_true",
        help="Enable comparison of h5 files to reference files",
    )
    group.addoption(
        "--h5diff-generate-ref",
        help="directory to generate reference h5 files in, relative "
        "to location where py.test is run",
        action="store_true",
    )


def pytest_configure(config):

    if (
        config.getoption("--h5diff")
        or config.getoption("--h5diff-generate-ref") is not None
    ):
        config.pluginmanager.register(
            H5Comparison(config, config.getoption("--h5diff-generate-ref"))
        )


class H5File:
    @staticmethod
    def read(filename):
        return h5py.File(filename, "r")

    @staticmethod
    def move(ref_path, current_path, filename):
        if not os.path.exists(ref_path):
            os.mkdir(ref_path)
        for file in os.listdir(current_path):
            if file.startswith(filename) and (
                file.endswith(".h5") or file.endswith(".xdmf")
            ):
                shutil.copyfile(
                    os.path.join(current_path, file),
                    os.path.abspath(os.path.join(ref_path, file)),
                )

    @classmethod
    def compare(cls, ref_path, test_path, filename, atol=None, rtol=None):
        ref_files = []
        test_files = []
        for file in os.listdir(ref_path):
            if file.startswith(filename) and file.endswith(".h5"):
                ref_files.append(file)

        for file in os.listdir(test_path):
            if (
                file.startswith(filename)
                and "restart" not in file
                and file.endswith(".h5")
            ):
                test_files.append(file)

        if ref_files != test_files:
            raise Exception(
                f"""Reference fiels and files generated by the test are not the same
                                    Reference files:
                                    \t{ref_files}
                                    Generated files:
                                    \t{test_files}
            """
            )

        for file in ref_files:
            ref_file = cls.read(os.path.join(ref_path, file))
            test_file = cls.read(os.path.join(test_path, file))

            dataset = None

            def func(name, obj):
                if isinstance(obj, h5py.Dataset):
                    dataset = obj
                    assert test_file[name][...] == pytest.approx(
                        ref_file[name][...], rel=rtol, abs=atol
                    )

            try:
                ref_file.visititems(func)
            except AssertionError as exc:
                message = f"""
                    datatset: {dataset}
                    a: {os.path.join(ref_path, file)}
                    b: {os.path.join(test_path, file)}
                    {exc.args[0]}
                    """
                return False, message
        return True, ""


class H5Comparison:

    def __init__(self, config, build_ref):
        self.config = config
        self.build_ref = build_ref

    def pytest_runtest_setup(self, item):

        compare = item.get_closest_marker("h5diff")

        if compare is None:
            return

        extension = "h5"
        atol = compare.kwargs.get("atol", 1e-7)
        rtol = compare.kwargs.get("rtol", 1e-14)

        single_reference = compare.kwargs.get("single_reference", False)

        original = item.function

        @wraps(item.function)
        def item_function_wrapper(*args, **kwargs):

            reference_dir = os.path.join(
                os.path.dirname(item.fspath.strpath), "reference"
            )

            # Find test name to use as plot name
            pathname = kwargs["config"]["path"]

            if single_reference:
                filename = original.__name__
            else:
                filename = item.name
                filename = filename.replace("[", "_").replace("]", "_")
                filename = filename.rstrip("_")

            kwargs["config"]["filename"] = filename

            if not self.build_ref:
                result_dir = tempfile.mkdtemp()
                kwargs["config"]["path"] = result_dir

            # Run test and get figure object
            import inspect

            if inspect.ismethod(original):  # method
                original(*args[1:], **kwargs)
            else:  # function
                original(*args, **kwargs)

            # What we do now depends on whether we are generating the reference
            # files or simply running the test.
            if self.build_ref:
                ref_path = os.path.join(reference_dir, pathname)

                if not os.path.exists(ref_path):
                    os.makedirs(ref_path)

                H5File.move(ref_path, pathname, filename)

                shutil.rmtree(pathname)

                pytest.skip("Skipping test, since generating data")
            else:
                test_h5file = os.path.abspath(os.path.join(result_dir, filename))

                # Find path to baseline array
                baseline_path_ref = os.path.abspath(
                    os.path.join(
                        os.path.dirname(item.fspath.strpath), reference_dir, pathname
                    )
                )

                identical, msg = H5File.compare(
                    baseline_path_ref, result_dir, filename, atol=atol, rtol=rtol
                )

                if identical:
                    shutil.rmtree(result_dir)
                else:
                    raise Exception(msg)

        if item.cls is not None:
            setattr(item.cls, item.function.__name__, item_function_wrapper)
        else:
            item.obj = item_function_wrapper
