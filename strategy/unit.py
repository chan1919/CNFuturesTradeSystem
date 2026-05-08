from abc import ABC, abstractmethod


class AbstractUnit(ABC):
    def __init__(self, instrument_id: str, contract, params: dict):
        self.instrument_id = instrument_id
        self.contract = contract
        self.params = dict(params)
        self.enabled = False
        from strategy.position import Position
        self.position = Position(instrument_id=instrument_id)

    @abstractmethod
    def subscribe_market(self, md_gateway):
        ...

    @abstractmethod
    def on_tick(self, tick: dict):
        ...

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

    @abstractmethod
    def _process_tick(self, tick: dict):
        ...


class RealUnit(AbstractUnit):
    def subscribe_market(self, md_gateway):
        md_gateway.subscribe(self.contract.ctp_id)

    def on_tick(self, tick: dict):
        if not self.enabled:
            return
        if tick.get("instrument_id") != self.contract.symbol:
            return
        self._process_tick(tick)

    def _process_tick(self, tick: dict):
        pass


class SyntheticUnit(AbstractUnit):
    def __init__(self, name: str, components: list, weights: list[float], params: dict):
        super().__init__(instrument_id=name, contract=None, params=params)
        self.formula = " + ".join(
            f"{c.symbol}*{w}" for c, w in zip(components, weights)
        )
        self.components = components
        self.weights = weights
        self._price_cache: dict[str, float] = {}

    def subscribe_market(self, md_gateway):
        for comp in self.components:
            md_gateway.subscribe(comp.ctp_id)

    def on_tick(self, tick: dict):
        if not self.enabled:
            return

        for comp in self.components:
            if tick.get("instrument_id") == comp.symbol:
                self._price_cache[comp.symbol] = tick["last_price"]
                break

        if len(self._price_cache) == len(self.components):
            synthetic_price = self._compute_price()
            tick = dict(tick)
            tick["instrument_id"] = self.instrument_id
            tick["synthetic_price"] = synthetic_price
            self._process_tick(tick)

    def _compute_price(self) -> float:
        return sum(
            w * self._price_cache[c.symbol]
            for w, c in zip(self.weights, self.components)
        )

    def _process_tick(self, tick: dict):
        pass

    def _reset_state(self):
        super()._reset_state()
        self._price_cache.clear()