import inspect
from enum import Enum
from functools import partial, wraps
import typing as t


NameOrInterface = t.Union[type, str]
Constructor = t.Union[t.Type, t.Callable]
ScopeFunction = t.Callable[[Constructor], t.Any]


class Container:
    """
    Dependency Injection container. It's passed as an argument of every dependency
    injection aware constructor.
    """

    def __init__(self, default_scope: 'Scopes' = None):
        self._registry = {}
        self._default_scope = default_scope

    @staticmethod
    def _get_registry_key(identifier: NameOrInterface, qualifier: t.Any = None) -> tuple:
        return identifier, qualifier,

    def register_by_name(self, name: str, constructor: Constructor, qualifier: t.Any = None):
        """Registering constructors by name and qualifier."""
        key = Container._get_registry_key(name, qualifier)
        if key in self._registry:
            raise ValueError(f'Ambiguous name: {name}.')
        self._registry[key] = constructor

    def find_by_name(self, name: str, qualifier: t.Any = None) -> t.Any:
        """Finding registered constructors by name."""
        key = Container._get_registry_key(name, qualifier)
        return self.get_object(self._registry.get(key))

    def get_object(self, constructor: Constructor) -> t.Any:
        """
        Method creates instance of registered constructor according to scope type
        and returns it.
        """
        scope_function = getattr(constructor, '__scope_type', self._default_scope)
        return scope_function(self, constructor)

    def find_by_interface(self, interface: type, qualifier: t.Any = None) -> t.Any:
        """Finding registered constructors by interface."""
        key = Container._get_registry_key(interface, qualifier)
        return self.get_object(self._registry.get(key))

    def register_by_interface(
            self,
            interface: type,
            constructor: Constructor,
            qualifier: t.Any = None
    ):
        """Registering constructors by interface and qualifier."""
        key = Container._get_registry_key(interface, qualifier)
        if key in self._registry:
            raise ValueError(f'Ambiguous interface: {interface}.')
        self._registry[key] = constructor

    def instance_scope(self, constructor: Constructor) -> t.Any:
        """Every injection makes a new instance."""
        return constructor()


class Scopes(Enum):
    INSTANCE: ScopeFunction = partial(Container.instance_scope)

    def __call__(self, container: Container, constructor: Constructor):
        return self.value(container, constructor)

    def __repr__(self):
        return f"<Scopes.{self.name}>"


def scope(scope_type: Scopes) -> t.Callable:
    def decorator(obj: t.Callable) -> t.Callable:
        obj.__scope_function = scope_type
        return obj
    return decorator


class Inject:
    """
    A descriptor for injecting dependencies as properties
    """

    container: Container = None
    type_: t.Type = None

    def __init__(self, name: str = None, interface: t.Type = None, qualifier: t.Any = None):
        self.name = name
        self.interface = interface
        self.qualifier = qualifier

    def __get__(self, instance: t.Any, owner: t.Type) -> t.Any:
        if instance is None:
            return self

        if self.container is None:
            self.container = instance.container

        return _find_object(
            self.container, self.name, self.interface or self.type_, self.qualifier
        )

    def __set_name__(self, owner: t.Type, name: str) -> None:
        self.type_ = owner.__annotations__.get(name) if hasattr(owner, '__annotations__') else None


def _find_object(container, name, interface, qualifier):
    if name:
        return container.find_by_name(name, qualifier)
    elif interface:
        return container.find_by_interface(interface, qualifier)
    else:
        raise TypeError('Missing name or interface for Inject.')


def inject(fun: t.Callable) -> t.Callable:
    """
    A decorator for injecting dependencies into methods,

    """
    signature = inspect.signature(fun)

    annotations: t.Dict[str, t.Any] = {}
    for name, param in signature.parameters.items():
        if name == 'self':
            continue
        else:
            default = param.default
            if isinstance(default, Inject):
                annotations[name] = (
                    param.annotation if param.annotation is not param.empty else None,
                    default
                )

    @wraps(fun)
    def wrapper(*args, **kwargs):
        container = getattr(args[0], 'container', None)

        if not container:
            raise ValueError('Container not provided.')

        for name_, data in annotations.items():
            if name_ not in kwargs:
                annotation, inject_instance = data
                kwargs[name_] = _find_object(
                    container,
                    inject_instance.name,
                    annotation or inject_instance.interface,
                    inject_instance.qualifier
                )

        return fun(*args, **kwargs)

    return wrapper