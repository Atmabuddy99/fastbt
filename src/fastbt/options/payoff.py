"""
The options payoff module
"""
from typing import List, Optional, Union
from enum import Enum
from pydantic import BaseModel, PrivateAttr, root_validator
import logging
from collections import Counter


class Opt(str, Enum):
    CALL = "c"
    PUT = "p"
    FUTURE = "f"
    HOLDING = "h"


class Side(Enum):
    BUY = 1
    SELL = -1


class OptionContract(BaseModel):
    """
    A basic option contract
    Could also include futures and holdings
    strike
        strike price of the contract.
        For futures/holdings, enter the price at which the
        contract is entered into
    option
        type of option contract could be call,put,future or holding
    side
        buy or sell/ 1 for buy and -1 for sell
    premium
        premium in case of an option
    quantity
        quantity of the contract
    """

    strike: Union[int, float]
    option: Opt
    side: Side
    premium: float = 0.0
    quantity: int = 1

    @root_validator
    def premium_check(cls, values):
        # Premium mandatory for call and put options
        option = values.get("option")
        premium = values.get("premium")
        if option in (Opt.CALL, Opt.PUT):
            if premium == 0.0:
                raise ValueError(f"Premium mandatory for {option} option")
        return values

    def value(self, spot: float) -> float:
        """
        Calculate the value of this contract given the spot
        at expiry for a single quantity
        """
        if self.option == Opt.CALL:
            return max(spot - self.strike, 0)
        elif self.option == Opt.PUT:
            return max(self.strike - spot, 0)
        else:
            return spot - self.strike

    def net_value(self, spot: float) -> float:
        """
        Return the net value for this contract given the
        spot price at expiry
        """
        val = self.value(spot=spot)
        if self.option in (Opt.CALL, Opt.PUT):
            return (val - self.premium) * self.side.value * self.quantity
        else:
            return val * self.side.value * self.quantity


class OptionPayoff(BaseModel):
    """
    A simple class for calculating option payoffs
    given spot prices and options
    1) Add your options with the add method
    2) Provide a spot price
    3) Call calculate to get the payoff for this spot price
    Note
    -----
    This class only does a simple arithmetic for the option and
    doesn't include any calculations for volatility or duration.
    It's assumed that the option is exercised at expiry and it
    doesn't have any time value
    spot
        spot price of the instrument
    lot_size
        lot size of the instrument for futures and options contract
    """

    spot: float = 0.0
    lot_size: int = 1
    _options: List[OptionContract] = PrivateAttr(default_factory=list)

    def add(self, contract: OptionContract) -> None:
        """
        Add an option contract
        """
        self._options.append(contract)

    def add_contract(
        self,
        strike: float,
        opt_type: Opt = Opt.CALL,
        side: Side = Side.BUY,
        premium: float = 0.0,
        qty: int = 1,
    ) -> None:
        """
        Add an option
        strike
            strike price of the options
        opt_type
            option type - c for call and p for put
        position
            whether you are Buying or Selling the option
            B for buy and S for sell
        premium
            option premium
        qty
            quantity of options contract
        """
        contract = OptionContract(
            strike=strike, option=opt_type, side=side, premium=premium, quantity=qty
        )
        self._options.append(contract)

    @property
    def options(self) -> List[OptionContract]:
        """
        return the list of options
        """
        return self._options

    @property
    def net_positions(self) -> Counter:
        """
        returns the net positions for each type of contract
        call,put,futures,holdings
        """
        positions: Counter = Counter()
        for contract in self.options:
            quantity = contract.quantity * contract.side.value * self.lot_size
            positions[contract.option] += quantity
        return positions

    @property
    def has_naked_positions(self) -> bool:
        """
        returns True if there is a naked position
        Note
        -----
        1) Positions are considered naked if there are outstanding sell contracts
        2) Only CALL and PUT options are considered. Use `is_fully_hedged` to include futures and short selling
        """
        positions = self.net_positions
        if positions[Opt.CALL] < 0:
            return True
        elif positions[Opt.PUT] < 0:
            return True
        else:
            return False

    def clear(self) -> None:
        """
        Clear all options
        """
        self._options = []

    def payoff(self, spot: Optional[float] = None) -> float:
        """
        Calculate the payoff given the spot price
        """
        if not spot:
            spot = self.spot
        if len(self.options) == 0:
            logging.debug("No contracts added, nothing to calculate")
            return 0.0
        return sum(
            [contract.net_value(spot) * self.lot_size for contract in self.options]
        )

    def simulate(self, spot: Union[List[float], List[int]]) -> List[float]:
        """
        Simulate option payoff for different spot prices
        """
        return [self.payoff(spot=price) for price in spot]
