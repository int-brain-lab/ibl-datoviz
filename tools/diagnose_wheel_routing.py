"""Print raw and union wheel delivery counts without creating a GPU context.

Run with the configured Datoviz native environment. One emitted wheel event
should reach each raw or union subscriber once, regardless of gesture handlers.
This diagnostic records the behavior; it does not change or deduplicate input.
"""

from __future__ import annotations

import json

import datoviz as dvz


def inspect_delivery(handler_count: int) -> dict:
    """Emit one timestamped wheel event and retain callbacks through teardown."""
    router = dvz.dvz_input_router()
    if not router:
        raise RuntimeError('input router allocation failed')
    handlers, subscriptions, raw, union = [], [], [], []

    def record(target, pointer):
        target.append({
            'type': pointer.type,
            'timestamp_ns': pointer.timestamp_ns,
            'delta': list(pointer.content.w.dir),
        })

    def on_pointer(_router, event, _user):
        record(raw, event.contents)

    def on_event(_router, event, _user):
        if event.contents.type == dvz.DVZ_INPUT_EVENT_POINTER:
            record(union, event.contents.content.pointer)

    try:
        for _ in range(handler_count):
            handler = dvz.dvz_pointer_gesture_handler(router)
            if not handler:
                raise RuntimeError('gesture handler allocation failed')
            handlers.append(handler)
        for subscribe, callback in (
            (dvz.dvz_input_subscribe_pointer, on_pointer),
            (dvz.dvz_input_subscribe_event, on_event),
        ):
            subscription = subscribe(router, callback, None)
            if not subscription:
                raise RuntimeError('input subscription failed')
            subscriptions.append(subscription)
        dvz.dvz_pointer_emit_wheel(
            router, 10, 20, 100, 100, 0, -1, 0, 1, 123456789, None,
        )
        return {
            'gesture_handlers': handler_count,
            'raw_count': len(raw),
            'union_count': len(union),
            'raw_events': raw,
            'union_events': union,
            'expected_count_per_subscriber': 1,
        }
    finally:
        for subscription in reversed(subscriptions):
            dvz.dvz_input_unsubscribe(router, subscription)
        for handler in reversed(handlers):
            dvz.dvz_pointer_gesture_handler_destroy(handler)
        dvz.dvz_input_router_destroy(router)


if __name__ == '__main__':
    print(json.dumps({
        'datoviz_facade': dvz.__file__,
        'cases': [inspect_delivery(count) for count in (0, 1, 2)],
    }, indent=2))
