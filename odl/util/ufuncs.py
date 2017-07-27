﻿# Copyright 2014-2017 The ODL contributors
#
# This file is part of ODL.
#
# This Source Code Form is subject to the terms of the Mozilla Public License,
# v. 2.0. If a copy of the MPL was not distributed with this file, You can
# obtain one at https://mozilla.org/MPL/2.0/.

"""Universal functions (ufuncs) for ODL-wrapped arrays.

These functions are internal and should only be used as methods on
`TensorSpace` type spaces.

See `numpy.ufuncs
<http://docs.scipy.org/doc/numpy/reference/ufuncs.html>`_
for more information.

Notes
-----
The default implementation of these methods uses the ``__array_ufunc__``
dispatch machinery `introduced in Numpy 1.13
<https://github.com/charris/numpy/blob/master/doc/source/reference/\
arrays.classes.rst#special-attributes-and-methods>`_.
"""

# Imports for common Python 2/3 codebase
from __future__ import print_function, division, absolute_import
from future import standard_library
standard_library.install_aliases()

import numpy as np
import re


__all__ = ('TensorSpaceUfuncs', 'NumpyTensorSpaceUfuncs',
           'DiscreteLpUfuncs', 'ProductSpaceUfuncs')


# Some are ignored since they don't cooperate with dtypes, needs fix
RAW_UFUNCS = ['absolute', 'add', 'arccos', 'arccosh', 'arcsin', 'arcsinh',
              'arctan', 'arctan2', 'arctanh', 'bitwise_and', 'bitwise_or',
              'bitwise_xor', 'ceil', 'conj', 'copysign', 'cos', 'cosh',
              'deg2rad', 'divide', 'equal', 'exp', 'exp2', 'expm1', 'floor',
              'floor_divide', 'fmax', 'fmin', 'fmod', 'greater',
              'greater_equal', 'hypot', 'invert', 'isfinite', 'isinf', 'isnan',
              'left_shift', 'less', 'less_equal', 'log', 'log10', 'log1p',
              'log2', 'logaddexp', 'logaddexp2', 'logical_and', 'logical_not',
              'logical_or', 'logical_xor', 'maximum', 'minimum', 'mod', 'modf',
              'multiply', 'negative', 'not_equal', 'power',
              'rad2deg', 'reciprocal', 'remainder', 'right_shift', 'rint',
              'sign', 'signbit', 'sin', 'sinh', 'sqrt', 'square', 'subtract',
              'tan', 'tanh', 'true_divide', 'trunc']
# ,'isreal', 'iscomplex', 'ldexp', 'frexp'

# Add some standardized information
UFUNCS = []
for name in RAW_UFUNCS:
    ufunc = getattr(np, name)
    n_in, n_out = ufunc.nin, ufunc.nout
    descr = ufunc.__doc__.splitlines()[2]
    # Numpy occasionally uses single ticks for doc, we only use them for links
    descr = re.sub('`+', '``', descr)
    doc = descr + """

See Also
--------
numpy.{}
""".format(name)
    UFUNCS.append((name, n_in, n_out, doc))

# TODO: add the following reductions (to the CUDA implementation):
# ['var', 'trace', 'tensordot', 'std', 'ptp', 'mean', 'diff', 'cumsum',
#  'cumprod', 'average']


# --- Wrappers for base tensors --- #


def wrap_ufunc_base(name, n_in, n_out, doc):
    """Return ufunc wrapper for implementation-agnostic ufunc classes."""
    ufunc = getattr(np, name)
    if n_in == 1:
        if n_out == 1:
            def wrapper(self, out=None):
                return self.elem.__array_ufunc__(
                    ufunc, '__call__', self.elem, out=(out,))

        elif n_out == 2:
            def wrapper(self, out1=None, out2=None):
                return self.elem.__array_ufunc__(
                    ufunc, '__call__', self.elem, out=(out1, out2))

        else:
            raise NotImplementedError

    elif n_in == 2:
        if n_out == 1:
            def wrapper(self, x2, out=None):
                return self.elem.__array_ufunc__(
                    ufunc, '__call__', self.elem, x2, out=(out,))

        else:
            raise NotImplementedError
    else:
        raise NotImplementedError

    wrapper.__name__ = wrapper.__qualname__ = name
    wrapper.__doc__ = doc
    return wrapper


class TensorSpaceUfuncs(object):

    """Ufuncs for `Tensor` objects.

    Internal object, should not be created except in `Tensor`.
    """

    def __init__(self, elem):
        """Create ufunc wrapper for elem."""
        self.elem = elem

    # Reductions for backwards compatibility

    def sum(self, axis=None, dtype=None, out=None, keepdims=False):
        """Return the sum of ``self``.

        See Also
        --------
        numpy.sum
        prod
        """
        return self.elem.__array_ufunc__(
            np.add, 'reduce', self.elem,
            axis=axis, dtype=dtype, out=(out,), keepdims=keepdims)

    def prod(self, axis=None, dtype=None, out=None, keepdims=False):
        """Return the product of ``self``.

        See Also
        --------
        numpy.prod
        sum
        """
        return self.elem.__array_ufunc__(
            np.multiply, 'reduce', self.elem,
            axis=axis, dtype=dtype, out=(out,), keepdims=keepdims)

    def min(self, axis=None, dtype=None, out=None, keepdims=False):
        """Return the minimum of ``self``.

        See Also
        --------
        numpy.amin
        max
        """
        return self.elem.__array_ufunc__(
            np.minimum, 'reduce', self.elem,
            axis=axis, dtype=dtype, out=(out,), keepdims=keepdims)

    def max(self, axis=None, dtype=None, out=None, keepdims=False):
        """Return the maximum of ``self``.

        See Also
        --------
        numpy.amax
        min
        """
        return self.elem.__array_ufunc__(
            np.maximum, 'reduce', self.elem,
            axis=axis, dtype=dtype, out=(out,), keepdims=keepdims)


# Add ufunc methods to ufunc class
for name, n_in, n_out, doc in UFUNCS:
    method = wrap_ufunc_base(name, n_in, n_out, doc)
    setattr(TensorSpaceUfuncs, name, method)


def wrap_reduction_numpy(name, doc):
    """Return reduction wrapper for Numpy-based ufunc classes."""
    wrapped = getattr(np, name)

    def wrapper(self, axis=None, out=None, keepdims=False, **kwargs):
        from odl.space.npy_tensors import (NumpyTensorSpaceArrayWeighting,
                                           NumpyTensorSpaceNoWeighting)
        # Avoid giving arrays explicitly through kwargs
        kwargs.pop('a', None)
        kwargs.pop('b', None)
        kwargs.pop('out', None)

        # Put positional arguments with defaults into kwargs
        if axis is not None:
            kwargs['axis'] = axis
        kwargs['keepdims'] = keepdims

        # Get dtype parameter present in some reductions since it's
        # relevant for the output space
        dtype = kwargs.get('dtype', self.elem.dtype)

        if out is None:
            out_arr = wrapped(self.elem, **kwargs)
            if np.isscalar(out_arr):
                return out_arr

            # For the TensorSpace variant, we additionally pass `exponent`
            # and `weight` to the constructor
            extra_args = {}
            exponent = getattr(self.elem.space, 'exponent', None)
            if exponent is not None:
                extra_args['exponent'] = exponent
            weighting = getattr(self.elem.space, 'weighting', None)
            if weighting is not None:
                # Array weighting cannot be propagated since sizes don't
                # match any longer
                if isinstance(weighting, NumpyTensorSpaceArrayWeighting):
                    weighting = NumpyTensorSpaceNoWeighting(exponent=exponent)
                extra_args['weighting'] = weighting

            out_space_constr = type(self.elem.space)
            out_space = out_space_constr(out_arr.shape, dtype, self.elem.order,
                                         **extra_args)
            return out_space.element(out_arr)
        else:
            wrapped(self.elem, out=out.data, **kwargs)
            return out

    wrapper.__name__ = wrapper.__qualname__ = name
    wrapper.__doc__ = doc
    return wrapper


# --- Wrappers for DiscreteLp --- #


# For DiscreteLP, basically the ufunc mechanism can be propagated from its
# `tensor` attribute.
def wrap_ufunc_discretelp(name, n_in, n_out, doc):
    """Return ufunc wrapper for `DiscreteLpUfuncs`."""
    if n_in == 1:
        if n_out == 0:
            def wrapper(self):
                method = getattr(self.elem.tensor.ufuncs, name)
                return self.elem.space.element(method())

        elif n_out == 1:
            def wrapper(self, out=None):
                method = getattr(self.elem.tensor.ufuncs, name)
                if out is None:
                    return self.elem.space.element(method())
                else:
                    method(out=out.tensor)
                    return out

        elif n_out == 2:
            def wrapper(self, out1=None, out2=None):
                method = getattr(self.elem.tensor.ufuncs, name)
                if out1 is None:
                    out1 = self.elem.space.element()
                if out2 is None:
                    out2 = self.elem.space.element()

                y1, y2 = method(out1.tensor, out2.tensor)
                return out1, out2

        else:
            raise NotImplementedError

    elif n_in == 2:
        if n_out == 1:
            def wrapper(self, x2, out=None):
                if x2 in self.elem.space:
                    x2 = x2.tensor

                method = getattr(self.elem.tensor.ufuncs, name)
                if out is None:
                    return self.elem.space.element(method(x2))
                else:
                    method(x2, out.tensor)
                    return out

        else:
            raise NotImplementedError
    else:
        raise NotImplementedError

    wrapper.__name__ = wrapper.__qualname__ = name
    wrapper.__doc__ = doc
    return wrapper


class DiscreteLpUfuncs(TensorSpaceUfuncs):

    """Ufuncs for `DiscreteLpElement` objects.

    Internal object, should not be created except in `DiscreteLpElement`.
    """


# Add ufunc methods to ufunc class
for name, n_in, n_out, doc in UFUNCS:
    method = wrap_ufunc_discretelp(name, n_in, n_out, doc)
    setattr(DiscreteLpUfuncs, name, method)


# --- Wrappers for Product space elements --- #


def wrap_ufunc_productspace(name, n_in, n_out, doc):
    """Return ufunc wrapper for `ProductSpaceUfuncs`."""
    if n_in == 1:
        if n_out == 0:
            def wrapper(self):
                result = [getattr(x.ufuncs, name)() for x in self.elem]
                return self.elem.space.element(result)

        elif n_out == 1:
            def wrapper(self, out=None):
                if out is None:
                    result = [getattr(x.ufuncs, name)() for x in self.elem]
                    return self.elem.space.element(result)
                else:
                    for x, out_x in zip(self.elem, out):
                        getattr(x.ufuncs, name)(out=out_x)
                    return out

        elif n_out == 2:
            def wrapper(self, out1=None, out2=None):
                if out1 is None:
                    out1 = self.elem.space.element()
                if out2 is None:
                    out2 = self.elem.space.element()
                for x, out1_x, out2_x in zip(self.elem, out1, out2):
                    getattr(x.ufuncs, name)(out1=out1_x, out2=out2_x)
                return out1, out2

        else:
            raise NotImplementedError

    elif n_in == 2:
        if n_out == 1:
            def wrapper(self, x2, out=None):
                if x2 in self.elem.space:
                    if out is None:
                        result = [getattr(x.ufuncs, name)(x2p)
                                  for x, x2p in zip(self.elem, x2)]
                        return self.elem.space.element(result)
                    else:
                        for x, x2p, outp in zip(self.elem, x2, out):
                            getattr(x.ufuncs, name)(x2p, out=outp)
                        return out
                else:
                    if out is None:
                        result = [getattr(x.ufuncs, name)(x2)
                                  for x in self.elem]
                        return self.elem.space.element(result)
                    else:
                        for x, outp in zip(self.elem, out):
                            getattr(x.ufuncs, name)(x2, out=outp)
                        return out

        else:
            raise NotImplementedError
    else:
        raise NotImplementedError

    wrapper.__name__ = wrapper.__qualname__ = name
    wrapper.__doc__ = doc
    return wrapper


class ProductSpaceUfuncs(object):

    """Ufuncs for `ProductSpaceElement` objects.

    Internal object, should not be created except in `ProductSpaceElement`.
    """
    def __init__(self, elem):
        """Create ufunc wrapper for ``elem``."""
        self.elem = elem


# Add ufunc methods to ufunc class
for name, n_in, n_out, doc in UFUNCS:
    method = wrap_ufunc_productspace(name, n_in, n_out, doc)
    setattr(ProductSpaceUfuncs, name, method)
