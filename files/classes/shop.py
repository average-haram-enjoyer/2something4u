import time

from sqlalchemy import *
from sqlalchemy.orm import relationship
from files.__main__ import Base


class ShopCategory(Base):

    __tablename__ = "shopcats"

    id = Column(Integer, primary_key=True)
    name = Column(String(50))
    description = Column(String(255))

    items = relationship("ShopItemDef",
                         primaryjoin="ShopItemDef.category_id == ShopCategory.id",
                         back_populates="category",
                         lazy="joined"
                         )

    @property
    def json_noitems(self):

        return {
            "id": self.id,
            "name": self.name,
            "description": self.description
        }

    @property
    def json(self):

        _json = self.json_noitems
        _json['items'] = [x.json for x in self.items]

        return _json


class ShopItemDef(Base):

    __tablename__ = "item_defs"

    id = Column(Integer, primary_key=True)
    name = Column(String(50))
    description = Column(String(255))
    icon_url = Column(String(255))
    created_utc = Column(Integer, default=0)
    price = Column(Integer)
    discount_price = Column(Integer, default=0)
    featured = Column(Boolean, default=False)
    category_id = Column(Integer, ForeignKey('shopcats.id'))

    category = relationship("ShopCategory",
                            primaryjoin="ShopItemDef.category_id == ShopCategory.id",
                            back_populates="items",
                            uselist=False)

    def __init__(self, **kwargs):

        if 'created_utc' not in kwargs:
            kwargs['created_utc'] = int(time.time())

        super().__init__(**kwargs)

    @property
    def age(self):
        now = int(time.time())

        return now - self.created_utc

    # show "new" label if younger than 3d
    @property
    def new(self):

        return self.age < self.created_utc+3*24*60*60

    @property
    def cost(self):
        if self.discount_price == 0 or self.discount_price >= self.price:
            return self.price
        else:
            return self.discount_price

    @property
    def json(self):

        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "icon": self.icon_url,
            "cost": self.cost,
            "discount": self.discount_price > 0,
            "featured": self.featured,
            "new": self.new,
            "category_name": self.category.name
        }


class ShopItem(Base):

    __tablename__ = "items"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    item_id = Column(Integer, ForeignKey('item_defs.id'))

    user = relationship("User", primaryjoin="ShopItem.user_id == User.id", uselist=False, lazy="joined")
    item = relationship("ShopItemDef", primaryjoin="ShopItem.item_id == ShopItemDef.id", uselist=False, lazy="joined")

    @property
    def json(self):

        return {
            "id": self.id,
            "item_id": self.item.id,
            "name": self.item.name,
            "description": self.item.description,
            "price": self.item.price
        }
