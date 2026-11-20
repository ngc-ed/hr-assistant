"""Ciclo de vida del proceso: los workers no sobreviven a su proceso padre."""

import multiprocessing
import os
import threading

POLL_SECONDS = 1.0


def exit_with_parent(poll_seconds: float = POLL_SECONDS) -> bool:
    """Hace que un worker termine cuando muere su proceso padre.

    En Windows, terminar al supervisor de uvicorn deja huérfanos a sus workers,
    que siguen sirviendo y ocupando el puerto. Fuera de un worker no hace nada.

    :param poll_seconds: Cada cuántos segundos se revisa al padre
    :type poll_seconds: float
    :return: ``True`` si se vigila al padre, ``False`` si no hay padre que vigilar
    :rtype: bool
    """
    parent = multiprocessing.parent_process()
    if parent is None:
        return False

    def watch() -> None:
        """Espera a que el padre muera y sale sin esperar a nadie."""
        while parent.is_alive():
            threading.Event().wait(poll_seconds)
        os._exit(0)

    threading.Thread(target=watch, daemon=True, name="parent-watch").start()
    return True
