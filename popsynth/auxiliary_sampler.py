import abc
import numpy as np


class AuxiliaryParameter(object):
    def __init__(self, default=None, vmin=None, vmax=None):

        self.name = None
        self._vmin = vmin
        self._vmax = vmax
        self._default = default
        
    @property
    def default(self):
        return self._default
        
    def __get__(self, obj, type=None) -> object:
        
        return obj._parameter_storage[self.name]

    def __set__(self, obj, value) -> None:
        

        if self._vmin is not None:
            assert (
                value >= self._vmin
            ), f"trying to set {self.x} to a value below {self._vmin} is not allowed"

        if self._vmax is not None:
            assert (
                value <= self._vmax
            ), f"trying to set {self.x} to a value above {self._vmax} is not allowed"

        obj._parameter_storage[self.name] = value


class AuxiliaryMeta(type):

    def __new__(mcls, name, bases, attrs, **kwargs):
        
        if "_parameter_storage" not in attrs:
            attrs["_parameter_storage"] = {}

        
        cls = super().__new__(mcls, name, bases, attrs, **kwargs)
        
        # Compute set of abstract method names
        abstracts = {
            name
            for name, value in attrs.items()
            if getattr(value, "__isabstractmethod__", False)
        }
        for base in bases:
            for name in getattr(base, "__abstractmethods__", set()):
                value = getattr(cls, name, None)
                if getattr(value, "__isabstractmethod__", False):
                    abstracts.add(name)
        cls.__abstractmethods__ = frozenset(abstracts)

        for k, v in attrs.items():
        
            if isinstance(v, AuxiliaryParameter):
                v.name = k
                attrs["_parameter_storage"][k] = v.default

        return cls

    def __subclasscheck__(cls, subclass):
        """Override for issubclass(subclass, cls)."""
        if not isinstance(subclass, type):
            raise TypeError("issubclass() arg 1 must be a class")
        # Check cache

        # Check the subclass hook
        ok = cls.__subclasshook__(subclass)
        if ok is not NotImplemented:
            assert isinstance(ok, bool)
            if ok:
                cls._abc_cache.add(subclass)
            else:
                cls._abc_negative_cache.add(subclass)
            return ok
        # Check if it's a direct subclass
        if cls in getattr(subclass, "__mro__", ()):
            cls._abc_cache.add(subclass)
            return True
        # Check if it's a subclass of a registered class (recursive)
        for rcls in cls._abc_registry:
            if issubclass(subclass, rcls):
                cls._abc_cache.add(subclass)
                return True
        # Check if it's a subclass of a subclass (recursive)
        for scls in cls.__subclasses__():
            if issubclass(subclass, scls):
                cls._abc_cache.add(subclass)
                return True
        # No dice; update negative cache
        cls._abc_negative_cache.add(subclass)
        return False


class AuxiliarySampler(object, metaclass=AuxiliaryMeta):
    def __init__(
        self, name, observed=True, uses_distance=False, uses_luminosity=False,
    ):

        self._name = name
        self._obs_name = "%s_obs" % name

        self._obs_values = None
        self._true_values = None
        self._is_observed = observed
        self._secondary_samplers = {}
        self._is_secondary = False
        self._has_secondary = False
        self._is_sampled = False
        self._selection = None
        self._uses_distance = uses_distance
        self._uses_luminoity = uses_luminosity

    def set_luminosity(self, luminosity):
        """FIXME! briefly describe function

        :param luminosity:
        :returns:
        :rtype:

        """

        self._luminosity = luminosity

    def set_distance(self, distance):
        """FIXME! briefly describe function

        :param distance:
        :returns:
        :rtype:

        """

        self._distance = distance

    def _apply_selection(self):
        """
        Default selection if none is specfied in child class
        """

        self._selection = np.ones_like(self._obs_values, dtype=bool)

    def set_secondary_sampler(self, sampler):
        """
        Allows the setting of a secondary sampler from which to derive values
        """

        # make sure we set the sampler as a secondary
        # this causes it to throw a flag in the main
        # loop if we try to add it again

        sampler.make_secondary()
        # attach the sampler to this class

        self._secondary_samplers[sampler.name] = sampler
        self._has_secondary = True

    def draw(self, size=1, verbose=True):
        """
        Draw the primary and secondary samplers. This is the main call.

        :param size: the number of samples to draw
        """
        # do not resample!
        if not self._is_sampled:
            if verbose:
                print("Sampling: %s" % self.name)

            if self._has_secondary:
                if verbose:
                    print("%s is sampling its secondary quantities" % self.name)

            for k, v in self._secondary_samplers.items():

                assert v.is_secondary, "Tried to sample a non-secondary, this is a bag"

                # we do not allow for the secondary
                # quantities to derive a luminosity
                # as it should be the last thing dervied

                v.draw(size=size, verbose=verbose)

            # Now, it is assumed that if this sampler depends on the previous samplers,
            # then those properties have been drawn

            self.true_sampler(size=size)

            if self._is_observed:

                self.observation_sampler(size)

            else:

                self._obs_values = self._true_values

            # check to make sure we sampled!
            assert (
                self.true_values is not None and len(self.true_values) == size
            ), f"{self.name} likely has a bad true_sampler function"
            assert (
                self.obs_values is not None and len(self.obs_values) == size
            ), f"{self.name} likely has a observation_sampler function"

            # now apply the selection to yourself
            # if there is nothing coded, it will be
            # list of all true

            self._apply_selection()

            self._is_sampled = True

    def make_secondary(self):

        self._is_secondary = True

    def get_secondary_properties(
        self,
        recursive_secondaries=None,
        graph=None,
        primary=None,
        spatial_distribution=None,
    ):
        """FIXME! briefly describe function

        :param recursive_secondaries:
        :returns:
        :rtype:

        """

        # if a holder was not passed, create one
        if recursive_secondaries is None:

            recursive_secondaries = {}

        # now collect each property. This should keep recursing
        if self._has_secondary:

            for k, v in self._secondary_samplers.items():

                if graph is not None:

                    graph.add_node(k, observed=False)
                    graph.add_edge(k, primary)

                    if v.observed:
                        graph.add_node(v.obs_name, observed=False)
                        graph.add_edge(k, v.obs_name)

                    if v.uses_distance:

                        self._graph.add_edge(spatial_distribution.name, k)

                recursive_secondaries = v.get_secondary_properties(
                    recursive_secondaries, graph, k, spatial_distribution
                )

        # add our own on
        recursive_secondaries[self._name] = {
            "true_values": self._true_values,
            "obs_values": self._obs_values,
            "selection": self._selection,
        }

        return recursive_secondaries

    @property
    def secondary_samplers(self):
        """
        Secondary samplers
        """

        return self._secondary_samplers

    @property
    def is_secondary(self):

        return self._is_secondary

    @property
    def has_secondary(self):

        return self._has_secondary

    @property
    def observed(self):
        """
        """
        return self._is_observed

    @property
    def name(self):
        return self._name

    @property
    def obs_name(self):
        return self._obs_name

    @property
    def true_values(self):
        """
        The true values

        :returns:
        :rtype:

        """

        return self._true_values

    @property
    def obs_values(self):
        """
        The observed values
        :returns:
        :rtype:

        """

        return self._obs_values

    @property
    def selection(self):
        """
        The selection function

        :returns:
        :rtype: np.ndarray

        """

        return self._selection

    @property
    def truth(self):
        return self._parameter_storage

    @property
    def uses_distance(self):
        return self._uses_distance

    @property
    def uses_luminosity(self):
        return self._luminosity

    @abc.abstractmethod
    def true_sampler(self, size=1):

        pass

    def observation_sampler(self, size=1):

        return self._true_values


class NonObservedAuxSampler(AuxiliarySampler):
    def __init__(self, name, uses_distance=False, uses_luminosity=False):

        super(NonObservedAuxSampler, self).__init__(
            name=name,
            observed=False,
            uses_distance=uses_distance,
            uses_luminosity=uses_luminosity,
        )


class DerivedLumAuxSampler(AuxiliarySampler):
    def __init__(self, name, uses_distance=False):
        """FIXME! briefly describe function

        :param name:
        :param sigma:
        :param observed:
        :returns:
        :rtype:

        """

        super(DerivedLumAuxSampler, self).__init__(
            name, observed=False, uses_distance=uses_distance
        )

    @abc.abstractmethod
    def compute_luminosity(self):

        raise RuntimeError("Must be implemented in derived class")
