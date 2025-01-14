import importlib
import importlib.machinery
import importlib.util
import os
import re
import tempfile

from mako import exceptions
from mako.template import Template

from .exc import CommandError


def template_to_file(template_file, dest, output_encoding, **kw):
    template = Template(filename=template_file)
    try:
        output = template.render_unicode(**kw).encode(output_encoding)
    except:
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as ntf:
            ntf.write(
                exceptions.text_error_template()
                .render_unicode()
                .encode(output_encoding)
            )
            fname = ntf.name
        raise CommandError(
            "Template rendering failed; see %s for a "
            "template-oriented traceback." % fname
        )
    else:
        with open(dest, "wb") as f:
            f.write(output)


def coerce_resource_to_filename(fname):
    """Interpret a filename as either a filesystem location or as a package
    resource.

    Names that are non absolute paths and contain a colon
    are interpreted as resources and coerced to a file location.

    """
    if not os.path.isabs(fname) and ":" in fname:
        import pkg_resources

        fname = pkg_resources.resource_filename(*fname.split(":"))
    return fname


def pyc_file_from_path(path):
    """Given a python source path, locate the .pyc."""

    candidate = importlib.util.cache_from_source(path)
    if os.path.exists(candidate):
        return candidate

    # even for pep3147, fall back to the old way of finding .pyc files,
    # to support sourceless operation
    filepath, ext = os.path.splitext(path)
    for ext in importlib.machinery.BYTECODE_SUFFIXES:
        if os.path.exists(filepath + ext):
            return filepath + ext
    else:
        return None


def load_python_file(dir_, filename):
    """Load a file from the given path as a Python module."""

    module_id = re.sub(r"\W", "_", filename)
    path = os.path.join(dir_, filename)
    _, ext = os.path.splitext(filename)
    if ext == ".py":
        if os.path.exists(path):
            module = load_module_py(module_id, path)
        else:
            pyc_path = pyc_file_from_path(path)
            if pyc_path is None:
                raise ImportError("Can't find Python file %s" % path)
            else:
                module = load_module_pyc(module_id, pyc_path)
    elif ext in (".pyc", ".pyo"):
        module = load_module_pyc(module_id, path)
    return module


def load_module_py(module_id, path):
    spec = importlib.util.spec_from_file_location(module_id, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_module_pyc(module_id, path):
    spec = importlib.util.spec_from_file_location(module_id, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
