import tkinter as tk
from tkinter import ttk, messagebox
import random
import pandas as pd
from datetime import datetime, timedelta

# -----------------------------------------------------------
# Глобальные настройки и параметры
# -----------------------------------------------------------

DRIVER_TYPE_A = "A"
DRIVER_TYPE_B = "B"

# По умолчанию зададим некоторые константы;
# часть из них будем считывать из GUI
WEEK_DAYS = 7
SHIFT_START_HOUR = 6
SHIFT_END_HOUR   = 3
ROUTE_MIN = 50
ROUTE_MAX = 70

WORK_HOURS_A = 8
WORK_HOURS_B = 12
LUNCH_TIME_A = timedelta(hours=1)
BREAK_INTERVAL_B = timedelta(hours=2)
SHORT_BREAK_B_RANGE = (15, 20)
LONG_BREAK_B = 40

PEAK_INTERVALS = [(7,9), (17,19)]  # будни (day_idx=0..4)
MUTATION_RATE = 0.2

# -----------------------------------------------------------
# Вспомогательные функции
# -----------------------------------------------------------

def is_weekday(day_idx):
    return day_idx < 5

def is_peak_hour(dt: datetime, day_idx: int):
    if not is_weekday(day_idx):
        return False
    h = dt.hour
    for (start_h, end_h) in PEAK_INTERVALS:
        if start_h <= h < end_h:
            return True
    return False

def random_route_duration():
    return timedelta(minutes=random.randint(ROUTE_MIN, ROUTE_MAX))

def get_day_start(base_date: datetime, day_idx: int) -> datetime:
    d = base_date + timedelta(days=day_idx)
    return datetime(d.year, d.month, d.day, SHIFT_START_HOUR, 0)

def get_day_end(base_date: datetime, day_idx: int) -> datetime:
    day_start = get_day_start(base_date, day_idx)
    # до 03:00 следующего дня => 21 час после 06:00
    return day_start + timedelta(hours=21)

# -----------------------------------------------------------
# Классы для линейного алгоритма
# -----------------------------------------------------------

class Driver:
    def __init__(self, driver_id, driver_type):
        self.driver_id = driver_id
        self.driver_type = driver_type
        if driver_type == DRIVER_TYPE_A:
            self.work_limit = WORK_HOURS_A
        else:
            self.work_limit = WORK_HOURS_B
        self.worked = timedelta(0)
        self.next_free_time = None
        self.last_break_time = None
        self.long_break_used = False

    def can_work_this_day(self, day_idx):
        if self.driver_type == DRIVER_TYPE_A:
            return True
        else:
            # B: 1 день работы / 2 выходных
            return (day_idx % 3) == (self.driver_id % 3)

    def can_take_route(self, start_dt, dur):
        if self.next_free_time and start_dt < self.next_free_time:
            return False
        if self.worked + dur > timedelta(hours=self.work_limit):
            return False
        return True

class Bus:
    def __init__(self, bus_id):
        self.bus_id = bus_id
        self.next_free_time = None

# -----------------------------------------------------------
# Линейный алгоритм
# -----------------------------------------------------------

def generate_day_schedule(day_idx, base_date, num_buses, num_drivers):
    day_start = get_day_start(base_date, day_idx)
    day_end   = get_day_end(base_date, day_idx)

    buses = []
    for b_id in range(1, num_buses+1):
        b = Bus(b_id)
        b.next_free_time = day_start
        buses.append(b)

    drivers = []
    for d_id in range(1, num_drivers+1):
        d_type = DRIVER_TYPE_A if (d_id % 2 == 0) else DRIVER_TYPE_B
        drv = Driver(d_id, d_type)
        drv.next_free_time = day_start
        drv.last_break_time = day_start
        drivers.append(drv)

    schedule = []

    while True:
        bus_obj = min(buses, key=lambda x: x.next_free_time)
        current_time = bus_obj.next_free_time
        if current_time >= day_end:
            break

        dur = random_route_duration()
        chosen_driver = None
        random.shuffle(drivers)

        for drv in drivers:
            if not drv.can_work_this_day(day_idx):
                continue
            if not drv.can_take_route(current_time, dur):
                continue

            # A: обед
            if drv.driver_type == DRIVER_TYPE_A:
                if drv.worked >= timedelta(hours=4) and drv.worked < timedelta(hours=5):
                    if is_peak_hour(current_time, day_idx):
                        continue
                    else:
                        lunch_start = max(drv.next_free_time, current_time)
                        lunch_end   = lunch_start + LUNCH_TIME_A
                        if lunch_end > day_end:
                            continue
                        drv.worked += LUNCH_TIME_A
                        drv.next_free_time = lunch_end
                        if lunch_end > current_time:
                            current_time = lunch_end

                if not drv.can_take_route(current_time, dur):
                    continue

            # B: перерыв
            if drv.driver_type == DRIVER_TYPE_B:
                time_since_break = current_time - drv.last_break_time
                if time_since_break >= BREAK_INTERVAL_B:
                    if not drv.long_break_used:
                        br_len = LONG_BREAK_B
                        drv.long_break_used = True
                    else:
                        br_len = random.randint(*SHORT_BREAK_B_RANGE)
                    br_td = timedelta(minutes=br_len)

                    br_start = max(drv.next_free_time, current_time)
                    br_end   = br_start + br_td
                    if br_end > day_end:
                        continue
                    drv.worked += br_td
                    drv.next_free_time = br_end
                    drv.last_break_time = br_end
                    if br_end > current_time:
                        current_time = br_end

                if not drv.can_take_route(current_time, dur):
                    continue

            chosen_driver = drv
            break

        if chosen_driver is None:
            bus_obj.next_free_time += timedelta(minutes=10)
            continue
        else:
            start_dt = current_time
            end_dt   = current_time + dur
            if end_dt > day_end:
                bus_obj.next_free_time = day_end
                continue

            bus_obj.next_free_time = end_dt + timedelta(minutes=15)
            chosen_driver.worked += dur
            chosen_driver.next_free_time = end_dt

            schedule.append({
                "DayIdx": day_idx,
                "Date":   start_dt.strftime("%Y-%m-%d"),
                "Start":  start_dt.strftime("%H:%M"),
                "End":    end_dt.strftime("%H:%M"),
                "Bus ID": bus_obj.bus_id,
                "Driver ID": chosen_driver.driver_id,
                "DriverType": chosen_driver.driver_type,
                "Duration": int(dur.total_seconds()//60),
                "IsPeak": is_peak_hour(start_dt, day_idx)
            })

    schedule.sort(key=lambda x: x["Start"])
    return schedule

def generate_linear_schedule_week(base_date_str, num_buses, num_drivers):
    base_date = datetime.strptime(base_date_str, "%Y-%m-%d")
    all_sched = []
    for day_idx in range(WEEK_DAYS):
        day_sched = generate_day_schedule(day_idx, base_date, num_buses, num_drivers)
        all_sched.extend(day_sched)
    all_sched.sort(key=lambda x: (x["DayIdx"], x["Date"], x["Start"]))
    return all_sched

# -----------------------------------------------------------
# Генетический алгоритм (упрощённо, но с учетом тех же правил)
# -----------------------------------------------------------

class GaDriver:
    def __init__(self, driver_id):
        self.driver_id = driver_id
        self.driver_type = DRIVER_TYPE_A if (driver_id % 2 == 0) else DRIVER_TYPE_B
        self.max_hours = WORK_HOURS_A if self.driver_type==DRIVER_TYPE_A else WORK_HOURS_B
        self.worked = timedelta(0)
        self.next_free_time = None
        self.last_break_time = None
        self.long_break_used = False

    def can_work_this_day(self, day_idx):
        if self.driver_type == DRIVER_TYPE_A:
            return True
        return (day_idx % 3) == (self.driver_id % 3)

    def can_take_route(self, start_dt, dur):
        if self.next_free_time and start_dt < self.next_free_time:
            return False
        if self.worked + dur > timedelta(hours=self.max_hours):
            return False
        return True

def generate_valid_day(day_idx: int, base_date: datetime, num_buses, num_drivers):
    day_start = get_day_start(base_date, day_idx)
    day_end   = get_day_end(base_date, day_idx)

    buses = []
    for b_id in range(1, num_buses+1):
        b = Bus(b_id)
        b.next_free_time = day_start
        buses.append(b)

    drivers = []
    for d_id in range(1, num_drivers+1):
        gd = GaDriver(d_id)
        gd.next_free_time = day_start
        gd.last_break_time = day_start
        drivers.append(gd)

    schedule = []
    # повышаем число маршрутов, чтобы не было слишком мало
    n_routes = random.randint(20, 40)

    for _ in range(n_routes):
        bus_obj = random.choice(buses)
        start_min = int((bus_obj.next_free_time - day_start).total_seconds()//60)
        if start_min < 0:
            start_min = 0
        total_min = int((day_end - day_start).total_seconds()//60)
        if start_min >= total_min:
            continue
        route_start_min = random.randint(start_min, total_min)
        start_dt = day_start + timedelta(minutes=route_start_min)
        dur = random_route_duration()
        end_dt = start_dt + dur
        if end_dt > day_end:
            continue

        random.shuffle(drivers)
        chosen = None
        for drv in drivers:
            if not drv.can_work_this_day(day_idx):
                continue
            if not drv.can_take_route(start_dt, dur):
                continue

            # A: обед
            if drv.driver_type == DRIVER_TYPE_A:
                if drv.worked >= timedelta(hours=4) and drv.worked < timedelta(hours=5):
                    if is_peak_hour(start_dt, day_idx):
                        continue
                    lunch_start = max(drv.next_free_time, start_dt)
                    lunch_end   = lunch_start + LUNCH_TIME_A
                    if lunch_end > day_end:
                        continue
                    drv.worked += LUNCH_TIME_A
                    drv.next_free_time = lunch_end
                    if lunch_end > start_dt:
                        start_dt = lunch_end
                    end_dt = start_dt + dur
                    if end_dt>day_end:
                        continue

            # B: перерывы
            if drv.driver_type == DRIVER_TYPE_B:
                time_since_break = start_dt - drv.last_break_time
                if time_since_break >= BREAK_INTERVAL_B:
                    if not drv.long_break_used:
                        br_len = LONG_BREAK_B
                        drv.long_break_used = True
                    else:
                        br_len = random.randint(*SHORT_BREAK_B_RANGE)
                    br_td = timedelta(minutes=br_len)
                    br_start = max(drv.next_free_time, start_dt)
                    br_end   = br_start + br_td
                    if br_end>day_end:
                        continue
                    drv.worked += br_td
                    drv.next_free_time = br_end
                    drv.last_break_time = br_end
                    if br_end>start_dt:
                        start_dt = br_end
                    end_dt = start_dt + dur
                    if end_dt>day_end:
                        continue

            if not drv.can_take_route(start_dt, dur):
                continue

            chosen = drv
            break

        if chosen is None:
            continue

        chosen.worked += dur
        chosen.next_free_time = end_dt
        bus_obj.next_free_time = end_dt + timedelta(minutes=15)

        schedule.append({
            "DayIdx": day_idx,
            "Date":   start_dt.strftime("%Y-%m-%d"),
            "Start":  start_dt.strftime("%H:%M"),
            "End":    end_dt.strftime("%H:%M"),
            "Bus ID": bus_obj.bus_id,
            "Driver ID": chosen.driver_id,
            "DriverType": chosen.driver_type,
            "Duration": int(dur.total_seconds()//60),
            "IsPeak": is_peak_hour(start_dt, day_idx)
        })

    schedule.sort(key=lambda x: x["Start"])
    return schedule

def generate_valid_week(base_date_str, num_buses, num_drivers):
    base_date = datetime.strptime(base_date_str, "%Y-%m-%d")
    full_sched = []
    for day_idx in range(WEEK_DAYS):
        day_sched = generate_valid_day(day_idx, base_date, num_buses, num_drivers)
        full_sched.extend(day_sched)
    full_sched.sort(key=lambda x: (x["DayIdx"], x["Date"], x["Start"]))
    return full_sched

def evaluate_schedule(schedule):
    df = pd.DataFrame(schedule)
    total_routes = len(df)
    peak_routes  = df["IsPeak"].sum() if not df.empty else 0
    unique_drv   = df["Driver ID"].nunique() if not df.empty else 1
    fit = 2*peak_routes + total_routes - 1.5*unique_drv
    return fit

def select_parent(population):
    pair = random.sample(population, 2)
    best = max(pair, key=evaluate_schedule)
    return best

def crossover(p1, p2):
    df1 = pd.DataFrame(p1)
    df2 = pd.DataFrame(p2)
    c1 = df1[df1["DayIdx"] <= 2]
    c2 = df2[df2["DayIdx"] >= 3]
    child_df = pd.concat([c1, c2], ignore_index=True)
    child_df.sort_values(by=["DayIdx","Date","Start"], inplace=True)
    return child_df.to_dict("records")

def mutate(schedule, num_buses, num_drivers, mutation_rate=0.2):
    import random
    if random.random() < mutation_rate and schedule:
        r = random.random()
        if r < 0.3:
            # Удаляем один маршрут
            idx = random.randint(0, len(schedule)-1)
            schedule.pop(idx)
        else:
            # Изменяем одного маршрута
            idx = random.randint(0, len(schedule)-1)
            new_drv = random.randint(1, num_drivers)
            schedule[idx]["Driver ID"] = new_drv
            schedule[idx]["DriverType"] = "A" if (new_drv % 2 == 0) else "B"
            schedule[idx]["Bus ID"] = random.randint(1, num_buses)

    # Сортируем
    schedule.sort(key=lambda x: (x["DayIdx"], x["Date"], x["Start"]))
    return schedule



def run_genetic(base_date_str, num_buses, num_drivers, pop_size=15, generations=20):
    population = []
    for _ in range(pop_size):
        ind = generate_valid_week(base_date_str, num_buses, num_drivers)
        population.append(ind)

    for gen in range(generations):
        new_pop = []
        for _ in range(pop_size):
            p1 = select_parent(population)
            p2 = select_parent(population)
            child = crossover(p1, p2)
            child = mutate(child, num_buses, num_drivers)
            new_pop.append(child)
        population = new_pop

    best_ind = max(population, key=evaluate_schedule)
    return best_ind

# -----------------------------------------------------------
# GUI на tkinter
# -----------------------------------------------------------

class AppGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Bus Scheduling GUI")

        # Параметры (слева: ввод)
        params_frame = ttk.LabelFrame(root, text=" Ввод данных ")
        params_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nw")

        # Поле "Дата начала"
        ttk.Label(params_frame, text="Начальная дата (YYYY-MM-DD):").grid(row=0, column=0, sticky="w")
        self.date_entry = ttk.Entry(params_frame, width=15)
        self.date_entry.insert(0, "2024-01-01")
        self.date_entry.grid(row=0, column=1, pady=5)

        # Количество маршруток
        ttk.Label(params_frame, text="Кол-во маршруток:").grid(row=1, column=0, sticky="w")
        self.buses_var = tk.StringVar(value="5")
        self.buses_entry = ttk.Entry(params_frame, textvariable=self.buses_var, width=10)
        self.buses_entry.grid(row=1, column=1, pady=5)

        # Количество водителей
        ttk.Label(params_frame, text="Кол-во водителей:").grid(row=2, column=0, sticky="w")
        self.drivers_var = tk.StringVar(value="12")
        self.drivers_entry = ttk.Entry(params_frame, textvariable=self.drivers_var, width=10)
        self.drivers_entry.grid(row=2, column=1, pady=5)

        # Кнопки для запуска алгоритмов
        buttons_frame = ttk.Frame(root)
        buttons_frame.grid(row=1, column=0, padx=10, pady=5, sticky="w")

        self.run_direct_btn = ttk.Button(buttons_frame, text="Линейный алгоритм", command=self.run_direct_algorithm)
        self.run_direct_btn.grid(row=0, column=0, padx=5)

        self.run_ga_btn = ttk.Button(buttons_frame, text="Генетический алгоритм", command=self.run_ga_algorithm)
        self.run_ga_btn.grid(row=0, column=1, padx=5)

        # Вывод результатов
        output_frame = ttk.LabelFrame(root, text=" Результат ")
        output_frame.grid(row=2, column=0, padx=10, pady=10, sticky="nw")

        self.output_text = tk.Text(output_frame, width=80, height=20)
        self.output_text.pack(padx=5, pady=5)

    def run_direct_algorithm(self):
        try:
            base_date_str = self.date_entry.get().strip()
            num_buses = int(self.buses_var.get())
            num_drivers = int(self.drivers_var.get())

            schedule = generate_linear_schedule_week(base_date_str, num_buses, num_drivers)
            df = pd.DataFrame(schedule)
            filename = "linear_schedule_week_gui.csv"
            df.to_csv(filename, index=False)

            total_routes = len(df)
            peak_routes = df["IsPeak"].sum()
            unique_drivers = df["Driver ID"].nunique()
            fit = evaluate_schedule(schedule)

            # Выводим результат в текстовое поле
            self.output_text.delete("1.0", tk.END)
            self.output_text.insert(tk.END, f"ЛИНЕЙНЫЙ АЛГОРИТМ\n")
            self.output_text.insert(tk.END, f"Файл сохранен: {filename}\n\n")
            self.output_text.insert(tk.END, f"Всего рейсов: {total_routes}\n")
            self.output_text.insert(tk.END, f"Рейсов в пик: {peak_routes}\n")
            self.output_text.insert(tk.END, f"Уникальных водителей: {unique_drivers}\n")
            self.output_text.insert(tk.END, f"Fitness: {fit:.2f}\n")

        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def run_ga_algorithm(self):
        try:
            base_date_str = self.date_entry.get().strip()
            num_buses = int(self.buses_var.get())
            num_drivers = int(self.drivers_var.get())

            # Параметры ГА можно ввести дополнительно в GUI,
            # для примера возьмём фиксированные
            pop_size = 15
            generations = 20

            best_ind = run_genetic(base_date_str, num_buses, num_drivers, pop_size, generations)
            df = pd.DataFrame(best_ind)
            filename = "best_genetic_schedule_week_gui.csv"
            df.to_csv(filename, index=False)

            total_routes = len(df)
            peak_routes = df["IsPeak"].sum()
            unique_drivers = df["Driver ID"].nunique()
            fit = evaluate_schedule(best_ind)

            self.output_text.delete("1.0", tk.END)
            self.output_text.insert(tk.END, f"ГЕНЕТИЧЕСКИЙ АЛГОРИТМ\n")
            self.output_text.insert(tk.END, f"Файл сохранен: {filename}\n\n")
            self.output_text.insert(tk.END, f"Всего рейсов: {total_routes}\n")
            self.output_text.insert(tk.END, f"Рейсов в пик: {peak_routes}\n")
            self.output_text.insert(tk.END, f"Уникальных водителей: {unique_drivers}\n")
            self.output_text.insert(tk.END, f"Fitness: {fit:.2f}\n")

        except Exception as e:
            messagebox.showerror("Ошибка", str(e))


# -----------------------------------------------------------
# Точка входа
# -----------------------------------------------------------
def main():
    root = tk.Tk()
    app = AppGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
