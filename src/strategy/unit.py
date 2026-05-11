from abc import ABC, abstractmethod

from src.common.position import Position


class AbstractUnit(ABC):
    def __init__(self, instrument_id: str, contract, params: dict):
        self.instrument_id = instrument_id
        self.contract = contract
        self.params = dict(params)
        self.enabled = False

        self.position = Position(instrument_id=instrument_id)

    @abstractmethod
    def subscribe_market(self, md_gateway): ...

    @abstractmethod
    def on_tick(self, tick: dict): ...

    def enable(self):
        self.enabled = True

    def disable(self):
        self.enabled = False

    def update_params(self, params: dict):
        self.params.update(params)

    def restart(self):
        self._reset_state()
        self.enable()

    def clear_position(self):
        pass

    def on_order(self, event):
        pass

    def on_trade(self, event):
        pass

    def _reset_state(self):
        pass

    def component_instrument_ids(self) -> set[str]:
        return set()

    @abstractmethod
    def _process_tick(self, tick: dict): ...


class RealUnit(AbstractUnit):
    def subscribe_market(self, md_gateway):
        md_gateway.subscribe(self.contract.instrument_id)

    def on_tick(self, tick: dict):
        if not self.enabled:
            return None
        if tick.get("instrument_id") != self.contract.instrument_id:
            return None
        self._process_tick(tick)
        return tick

    def _process_tick(self, tick: dict):
        pass


class SyntheticUnit(AbstractUnit):
    def __init__(self, name: str, components: list, weights: list[float], params: dict):
        super().__init__(instrument_id=name, contract=None, params=params)
        self.formula = " + ".join(
            f"{c.instrument_id}*{w}" for c, w in zip(components, weights)
        )
        self.components = components
        self.weights = weights
        self._component_ids = {component.instrument_id for component in components}
        self._price_cache: dict[str, float] = {}

    def subscribe_market(self, md_gateway):
        for comp in self.components:
            md_gateway.subscribe(comp.instrument_id)

    def on_tick(self, tick: dict):
        if not self.enabled:
            return None

        source_instrument_id = tick.get("instrument_id")
        if source_instrument_id not in self._component_ids:
            return None

        self._price_cache[source_instrument_id] = tick["last_price"]

        if len(self._price_cache) == len(self.components):
            synthetic_price = self._compute_price()
            synthetic_tick = dict(tick)
            synthetic_tick["source_instrument_id"] = source_instrument_id
            synthetic_tick["source_last_price"] = tick["last_price"]
            synthetic_tick["instrument_id"] = self.instrument_id
            synthetic_tick["last_price"] = synthetic_price
            synthetic_tick["synthetic_price"] = synthetic_price
            self._process_tick(synthetic_tick)
            return synthetic_tick
        return None

    def _compute_price(self) -> float:
        return sum(
            w * self._price_cache[c.instrument_id]
            for w, c in zip(self.weights, self.components)
        )

    def _process_tick(self, tick: dict):
        pass

    def component_instrument_ids(self) -> set[str]:
        return set(self._component_ids)

    def _reset_state(self):
        super()._reset_state()
        self._price_cache.clear()
