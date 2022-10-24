import json
from db import database
from typing import Tuple, Union
from sqlalchemy.exc import SQLAlchemyError
from db.model import EventTable, OrderTable


def dict_to_model(event_data: dict) -> Tuple[EventTable, Union[OrderTable, None]]:
    order = None
    order_data = event_data.pop("parameters", None)
    if order_data is not None:
        order = OrderTable(**order_data)
    event = EventTable(**event_data)
    return event, order


def insert_event(event, context):
    message_id_list = []
    event_list = []
    order_list = {}
    for data in event["Records"]:
        try:
            event_data = json.loads(data["body"])
            event, order = dict_to_model(event_data)
            event_list.append(event)
            if order is not None:
                event.order_id = order.order_id
                # event many : order one.
                if order.order_id not in order_list.keys():
                    order_list.update({order.order_id: order})
        except KeyError as e:
            # failed work - return SQS
            print("failed - key error")
            print(e)
            return {"batchItemFailures": message_id_list}

    db_session = database.get_db_session()

    db_session.add_all(event_list)
    if len(order_list) > 0:
        db_session.add_all(list(order_list.values()))

    try:
        db_session.flush()
        db_session.commit()
    except SQLAlchemyError as e:
        db_session.rollback()
        # failed work - return SQS
        print("failed - db")
        print(e)
        return {"batchItemFailures": message_id_list}
    finally:
        db_session.close()
        database.close_db()
    return None