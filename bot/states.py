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
    active_query = State()


class ForcedJoinAdd(StatesGroup):
    chat_id = State()
    title = State()
    invite_link = State()


class TicketCreate(StatesGroup):
    subject = State()
    text = State()


class TicketReply(StatesGroup):
    text = State()


class BuyerTicketReply(StatesGroup):
    text = State()


class DiscountCreate(StatesGroup):
    code = State()
    percent = State()


class PurchaseCoupon(StatesGroup):
    code = State()


class AdminUserWallet(StatesGroup):
    amount = State()
    confirm = State()


class AdminUserMessage(StatesGroup):
    text = State()


class Broadcast(StatesGroup):
    text = State()


class SupportEdit(StatesGroup):
    username = State()


class EarningEdit(StatesGroup):
    percent = State()
