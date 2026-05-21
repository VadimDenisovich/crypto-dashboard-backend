"""Канонические имена каналов Redis Pub/Sub.

Источник истины — `trade-engine-crypto/src/application/events.py`. Эти константы
должны совпадать побитово: если в движке появится новый канал или изменится имя,
правка вносится синхронно сюда. Никакие магические строки в коде, кроме этого
файла.
"""

# Каналы, на которые ПОДПИСАН бэкенд (издаёт движок)
NEW_TRADE = "engine.new_trade"
BALANCE_UPDATE = "engine.balance_update"
POSITIONS_UPDATE = "engine.positions_update"
ENGINE_STATUS = "engine.status"
STRATEGY_ERROR = "engine.strategy_error"
ENGINE_LOG = "engine.log"

ENGINE_CHANNELS: tuple[str, ...] = (
    NEW_TRADE,
    BALANCE_UPDATE,
    POSITIONS_UPDATE,
    ENGINE_STATUS,
    STRATEGY_ERROR,
    ENGINE_LOG,
)

# Каналы команд, которые ПУБЛИКУЕТ бэкенд (читает движок)
COMMAND_START = "engine.commands.start"
COMMAND_STOP = "engine.commands.stop"
COMMAND_UPDATE = "engine.commands.update"
