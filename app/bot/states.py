from aiogram.fsm.state import State, StatesGroup


class AddProduct(StatesGroup):
    waiting_for_url = State()
    choosing_threshold_type = State()
    waiting_for_min_price = State()
    waiting_for_percent = State()
