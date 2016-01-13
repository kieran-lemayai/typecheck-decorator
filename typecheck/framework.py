
import inspect
import typing as tg

################################################################################

_enabled = True


def disable():
    global _enabled
    _enabled = False

def enable():
    global _enabled
    _enabled = True

################################################################################

class TypeCheckError(Exception): pass


class TypeCheckSpecificationError(Exception): pass


class InputParameterError(TypeCheckError): pass


class ReturnValueError(TypeCheckError): pass

################################################################################

def is_GenericMeta_class(something):
    return (inspect.isclass(something) and
            type(something) == tg.GenericMeta)

class TypeVarNamespace:
    """
    TypeVarNamespace objects hold TypeVar bindings.

    Consists of two sub-namespaces:
    A dictionary holding pairs of a TypeVar object and a type object
    for the call-level scope of a single function call
    and a similar dictionary for the instance-level scope of bindings for the
    type parameters of generic classes.
    The latter is stored as attribute NS_ATTRIBUTE in the class instance itself.
    Most TypeVarNamespace objects will never be used after their creation.
    is_compatible() implements bound, covariance, and contravariance logic.
    """
    NS_ATTRIBUTE = '__tc_bindings__'

    def __init__(self, instance=None):
        """_instance is the self of the method call if the class is a tg.Generic"""
        self._ns = dict()
        self._instance = instance
        self._instance_ns = (self._instance and
                             self._instance.__dict__.get(self.NS_ATTRIBUTE))

    def bind(self, typevar, its_type):
        """
        Binds typevar to the type its_type.
        Binding occurs on the instance if the typevar is a TypeVar of the
        generic type of the instance, on call level otherwise.
        """
        assert type(typevar) == tg.TypeVar
        if self.is_generic_in(typevar):
            self.bind_to_instance(typevar, its_type)
        else:
            self._ns[typevar] = its_type

    def is_generic_in(self, typevar):
        if not is_GenericMeta_class(type(self._instance)):
            return False
        # TODO: Is the following really sufficient?:
        return typevar in self._instance.__parameters__

    def bind_to_instance(self, typevar, its_type):
        if self._instance_ns is None:  # we've not bound something previously:
            self._instance.__setattr__(self.NS_ATTRIBUTE, dict())
            self._instance_ns = self._instance.__dict__[self.NS_ATTRIBUTE]
        self._instance_ns[typevar] = its_type

    def is_bound(self, typevar):
        if typevar in self._ns:
            return True
        return self._instance_ns and typevar in self._instance_ns

    def binding_of(self, typevar):
        """Returns the type the typevar is bound to, or None."""
        if typevar in self._ns:
            return self._ns[typevar]
        if self._instance_ns and typevar in self._instance_ns:
            return self._instance_ns[typevar]
        return None

    def is_compatible(self, typevar, its_type):
        """
        Checks whether its_type conforms to typevar.
        If the typevar is not yet bound, it will be bound to its_type.
        """
        binding = self.binding_of(typevar)
        if (binding and typevar.__bound__ and
                not issubclass(binding, typevar.__bound__)):
            return False  # bound violation
        if binding is None:
            self.bind(typevar, its_type)
            return True  # initial binding
        elif typevar.__covariant__:
            return issubclass(its_type, binding)  # allowed subtype?
        elif typevar.__contravariant__:
            return issubclass(binding, its_type)  # allowed supertype?
        else:
            return binding == its_type  # must be exactly the same type

################################################################################

class Checker:
    class NoValue:
        def __str__(self):
            return "<no value>"

    no_value = NoValue()

    _registered = []

    @classmethod
    def register(cls, predicate, factory, prepend=False):
        """
        Adds another type X of typecheck annotations to the framework.
        predicate(annot) indicates whether annot has annotation type X;
        factory(annot) creates the appropriate typechecker instance.
        The checker type is normally added after the existing ones,
        but 'prepend' makes it come first.
        """
        if prepend:
            cls._registered.insert(0, (predicate, factory))
        else:
            cls._registered.append((predicate, factory))

    @classmethod
    def create(cls, annotation_or_checker):
        if isinstance(annotation_or_checker, cls):
            return annotation_or_checker  # is a checker already
        annotation = annotation_or_checker
        for predicate, factory in cls._registered:
            if predicate(annotation):
                return factory(annotation)
        else:
            return None

    def __call__(self, value, namespace):
        return self.check(value, namespace)


################################################################################

class TypeChecker(Checker):
    def __init__(self, cls):
        self._cls = cls

    def check(self, value, namespace):
        return isinstance(value, self._cls)

# Note: 'typing'-module checkers must register _before_ this one:
Checker.register(inspect.isclass, TypeChecker)

################################################################################

class optional(Checker):
    def __init__(self, check):
        self._check = Checker.create(check)

    def check(self, value, namespace):
        return (value is Checker.no_value or
                value is None or
                self._check.check(value, namespace))