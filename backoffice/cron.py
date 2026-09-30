"""
Expresiones cron de 5 campos (minuto hora día-del-mes mes día-de-la-semana), sin
dependencias externas. Admite *, */n, listas (1,15), rangos (1-5) y rangos con paso
(0-30/10). Día de la semana: 0 o 7 = domingo, 1 = lunes... Como en cron, si se
restringen a la vez el día del mes y el de la semana, basta con que se cumpla uno.
"""
import datetime

FIELDS = [
    ("minuto", 0, 59),
    ("hora", 0, 23),
    ("día del mes", 1, 31),
    ("mes", 1, 12),
    ("día de la semana", 0, 7),
]

DAY_NAMES = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"]


class CronError(ValueError):
    pass


def _parse_field(text, name, low, high):
    values = set()
    for part in text.split(","):
        step = 1
        if "/" in part:
            part, step_text = part.split("/", 1)
            if not step_text.isdigit() or int(step_text) < 1:
                raise CronError(f"Paso no válido en el {name}: {text}")
            step = int(step_text)
        if part == "*":
            start, end = low, high
        elif "-" in part:
            a, b = part.split("-", 1)
            if not (a.isdigit() and b.isdigit()):
                raise CronError(f"Rango no válido en el {name}: {text}")
            start, end = int(a), int(b)
        elif part.isdigit():
            start = end = int(part)
            if step > 1:
                end = high
        else:
            raise CronError(f"Valor no válido en el {name}: {text}")
        if not (low <= start <= end <= high):
            raise CronError(f"Fuera de rango en el {name} ({low}-{high}): {text}")
        values.update(range(start, end + 1, step))
    return values


class Cron:
    def __init__(self, expression):
        parts = expression.split()
        if len(parts) != 5:
            raise CronError("Una expresión cron tiene 5 campos: minuto hora día mes día-de-la-semana.")
        self.expression = " ".join(parts)
        parsed = [_parse_field(p, *field) for p, field in zip(parts, FIELDS)]
        self.minutes, self.hours, self.days, self.months, dows = parsed
        self.dows = {d % 7 for d in dows}
        self.days_restricted = parts[2] != "*"
        self.dows_restricted = parts[4] != "*"

    def _day_matches(self, day):
        if day.month not in self.months:
            return False
        dom = day.day in self.days
        dow = (day.weekday() + 1) % 7 in self.dows  # weekday(): lunes=0 → cron: lunes=1
        if self.days_restricted and self.dows_restricted:
            return dom or dow
        if self.days_restricted:
            return dom
        if self.dows_restricted:
            return dow
        return True

    def next_after(self, moment):
        """Primer instante estrictamente posterior a `moment` (aware) que cumple la expresión."""
        tz = moment.tzinfo
        start = moment.replace(second=0, microsecond=0) + datetime.timedelta(minutes=1)
        day = start.date()
        for _ in range(366 * 5):
            if self._day_matches(day):
                for hour in sorted(self.hours):
                    for minute in sorted(self.minutes):
                        candidate = datetime.datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz)
                        if candidate >= start:
                            return candidate
            day += datetime.timedelta(days=1)
        raise CronError(f"La expresión {self.expression} no se cumple nunca.")

    def describe(self):
        """Descripción en español de los casos habituales; si no, la propia expresión."""
        m, h, dom, mon, dow = self.expression.split()
        if dom == "*" and mon == "*" and dow == "*":
            if m == "*" and h == "*":
                return "Cada minuto"
            if m.startswith("*/") and h == "*":
                return f"Cada {m[2:]} minutos"
            if m.isdigit() and h == "*":
                return f"Cada hora, en el minuto {int(m)}"
            if m.isdigit() and h.isdigit():
                return f"Cada día a las {int(h):02d}:{int(m):02d}"
        if dom == "*" and mon == "*" and dow.isdigit() and m.isdigit() and h.isdigit():
            return f"Cada {DAY_NAMES[int(dow) % 7]} a las {int(h):02d}:{int(m):02d}"
        if dom.isdigit() and mon == "*" and dow == "*" and m.isdigit() and h.isdigit():
            return f"El día {int(dom)} de cada mes a las {int(h):02d}:{int(m):02d}"
        return f"cron «{self.expression}»"
