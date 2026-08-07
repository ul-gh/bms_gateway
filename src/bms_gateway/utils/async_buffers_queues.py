"""Async data structures."""

import asyncio
from typing import TYPE_CHECKING, override

if TYPE_CHECKING:
    from asyncio.events import AbstractEventLoop


class SingleItemQueue[ItemType]:
    """Buffering of sync input for async output, a single-item queue.

    This stores the latest value item, overwriting any previous input.
    Use where one task produces value items and one or more tasks consume these.

    Using get_nopop(), the latest item can be repeatedly retrieved.
    """

    def __init__(self) -> None:
        """Init SingleItemQueue."""
        self._loop: AbstractEventLoop = asyncio.get_running_loop()
        self._data: asyncio.Future[ItemType] = self._loop.create_future()

    async def get(self) -> ItemType:
        """Get the latest item and create a new future object."""
        data = await self._data
        self._data = self._loop.create_future()
        return data

    async def get_nopop(self) -> ItemType:
        """Get the latest item without creating a new future."""
        return await self._data

    def put_nowait(self, item: ItemType) -> None:
        """Set item as the future result."""
        try:
            self._data.set_result(item)
        # Try again with a new future object in case the latest item was not retrieved in time.
        except asyncio.InvalidStateError:
            self._data = self._loop.create_future()
            self._data.set_result(item)


class HybridFifoQueue[ItemType](asyncio.Queue[ItemType]):
    """FIFO storage queue which silently discards the oldest item when full.

    This is intended for coupling sync input and async output.
    Values can only be retrieved ONCE as they are removed from queue when read.

    Overflow of this queue when using sync input is prevented by
    discarding the oldest entry and retrying again.
    """

    def __init__(self, maxsize: int = 10) -> None:
        """Init AsyncReceiveQueue."""
        super().__init__(maxsize)

    @override
    def put_nowait(self, item: ItemType) -> None:
        """Callback called when a UDP datagram arrives."""
        try:
            super().put_nowait(item)
        # If queue is full, we first discard the oldest entry and try again.
        except asyncio.QueueFull:
            try:
                _ = super().get_nowait()
                super().put_nowait(item)
            # Queue could have been drained by reading in between.
            except asyncio.QueueEmpty:
                try:  # noqa: SIM105
                    super().put_nowait(item)
                # If above fails again (new data arrived in between emptying the
                # queue and putting in the newest value), discard more data.
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass
            # Same if more data arrived after dropping the first value.
            except asyncio.QueueFull:
                pass
