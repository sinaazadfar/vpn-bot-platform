from aiogram.fsm.state import State, StatesGroup


class WalletTopUp(StatesGroup):
    amount = State()
    screenshot = State()


class PricingEdit(StatesGroup):
    per_gb_price = State()
    three_month_extra_price = State()
    preset_discount = State()


class PurchaseUsername(StatesGroup):
    username = State()


class WalletAdjust(StatesGroup):
    target = State()
    amount = State()


class AdminUserSearch(StatesGroup):
    query = State()


class AdminUserWallet(StatesGroup):
    amount = State()


class AdminUserMessage(StatesGroup):
    text = State()


class Broadcast(StatesGroup):
    text = State()


class SupportEdit(StatesGroup):
    username = State()


class EarningEdit(StatesGroup):
    percent = State()
