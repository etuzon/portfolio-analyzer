/* Shared scheduling controls. Weekdays use Monday=0 through Sunday=6. */
(function (global) {
  "use strict";
  const instances = new WeakMap();
  const frequencies = ["minutely", "hourly", "daily", "weekly", "monthly"];
  const frequencyLabels = ["Every N minutes", "Every N hours", "Every day", "Days each week", "Days each month"];
  const weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
  const defaults = { frequency: "daily", interval: 1, hour: 8, minute: 0, weekdays: [0], month_days: [1] };

  function summary(settings, translate = (value) => value) {
    const c = { ...defaults, ...(settings.schedule_config || {}) };
    const text = (key, values = {}) => Object.entries(values).reduce((result, [name, value]) => result.replaceAll(`{${name}}`, String(value)), translate(key));
    if (!settings.enabled) return translate("Automatic schedule disabled");
    let result;
    const time = `${String(c.hour).padStart(2, "0")}:${String(c.minute).padStart(2, "0")}`;
    if (c.frequency === "minutely") result = text("Every {interval} minutes", { interval: c.interval });
    else if (c.frequency === "hourly") result = text("Every {interval} hours at minute {minute}", { interval: c.interval, minute: c.minute });
    else if (c.frequency === "weekly") result = text("{days} at {time}", { days: c.weekdays.map(day => translate(weekdays[day])).join(", "), time });
    else if (c.frequency === "monthly") result = text("Monthly on days {days} at {time}", { days: c.month_days.join(", "), time });
    else result = text("Every day at {time}", { time });
    return `${result} · ${settings.timezone || "UTC"}`;
  }

  function mount(container, settings = {}, options = {}) {
    const previous = instances.get(container);
    if (previous) {
      container.removeEventListener("change", previous.update);
      container.removeEventListener("input", previous.update);
    }
    const translate = options.translate || ((value) => value);
    const editable = options.editable !== false;
    const config = { ...defaults, ...(settings.schedule_config || {}) };
    const doc = container.ownerDocument;
    const node = (tag, className, text) => {
      const element = doc.createElement(tag);
      if (className) element.className = className;
      if (text !== undefined) element.textContent = translate(text);
      return element;
    };
    container.replaceChildren();
    container.classList.add("universal-scheduler");
    const controls = {};
    function inputField(name, title, type, value, min, max) {
      const label = node("label", "field scheduler-field");
      label.append(node("span", "", title));
      const input = node("input");
      input.type = type;
      input.value = value;
      input.dataset.scheduleField = name;
      if (min !== undefined) { input.min = String(min); input.max = String(max); input.step = "1"; }
      label.append(input);
      controls[name] = input;
      return label;
    }
    const enabledLabel = node("label", "scheduler-enabled");
    const enabled = node("input");
    enabled.type = "checkbox";
    enabled.checked = settings.enabled === true;
    enabled.disabled = !editable;
    enabled.dataset.scheduleField = "enabled";
    enabledLabel.append(enabled, node("span", "", "Automatic schedule"));
    container.append(enabledLabel);
    const fields = node("div", "scheduler-fields");
    const frequencyLabel = node("label", "field scheduler-frequency");
    frequencyLabel.append(node("span", "", "Frequency"));
    const frequency = node("select");
    frequency.dataset.scheduleField = "frequency";
    frequencies.forEach((value, index) => {
      const option = node("option", "", frequencyLabels[index]);
      option.value = value;
      frequency.append(option);
    });
    frequency.value = frequencies.includes(config.frequency) ? config.frequency : "daily";
    frequencyLabel.append(frequency);
    controls.frequency = frequency;
    const intervalLabel = inputField("interval", "Interval", "number", config.interval, 1, 59);
    const hourLabel = inputField("hour", "Hour", "number", config.hour, 0, 23);
    const minuteLabel = inputField("minute", "Minute", "number", config.minute, 0, 59);
    const timezoneLabel = inputField("timezone", "Timezone", "text", settings.timezone || "UTC");
    controls.timezone.dir = "ltr";
    controls.timezone.placeholder = "Asia/Jerusalem";
    fields.append(frequencyLabel, intervalLabel, hourLabel, minuteLabel, timezoneLabel);
    container.append(fields);
    function picker(name, title, values, selected, labels) {
      const fieldset = node("fieldset", "scheduler-picker");
      fieldset.append(node("legend", "", title));
      const grid = node("div", `scheduler-choices scheduler-${name}`);
      controls[name] = values.map((value, index) => {
        const label = node("label", "scheduler-choice");
        const input = node("input");
        input.type = "checkbox";
        input.value = String(value);
        input.checked = selected.includes(value);
        input.dataset.scheduleField = name;
        label.append(input, node("span", "", labels ? labels[index] : String(value)));
        grid.append(label);
        return input;
      });
      fieldset.append(grid);
      container.append(fieldset);
      return fieldset;
    }
    const weekly = picker("weekdays", "Days each week", [0, 1, 2, 3, 4, 5, 6], config.weekdays, weekdays);
    const monthly = picker("month_days", "Days each month", Array.from({ length: 31 }, (_, i) => i + 1), config.month_days);
    const monthNote = node("p", "section-note", "Dates that do not occur in a month are skipped.");
    container.append(monthNote);
    const preview = node("p", "scheduler-summary");
    preview.setAttribute("role", "status");
    preview.setAttribute("aria-live", "polite");
    const error = node("p", "scheduler-error");
    error.setAttribute("role", "alert");
    error.hidden = true;
    container.append(preview, error);
    const intervalNote = node("p", "section-note", "Minute intervals restart each hour; hour intervals restart each day.");
    container.append(intervalNote);
    const instance = { controls, enabled, translate, editable, error };
    instances.set(container, instance);
    function update() {
      const f = frequency.value;
      intervalLabel.hidden = intervalNote.hidden = !["minutely", "hourly"].includes(f);
      controls.interval.max = f === "hourly" ? "23" : "59";
      hourLabel.hidden = ["minutely", "hourly"].includes(f);
      minuteLabel.hidden = f === "minutely";
      weekly.hidden = f !== "weekly";
      monthly.hidden = monthNote.hidden = f !== "monthly";
      fields.querySelectorAll("input, select").forEach(input => { input.disabled = !editable || !enabled.checked || input.closest("label").hidden; });
      [...controls.weekdays, ...controls.month_days].forEach(input => { input.disabled = !editable || !enabled.checked || input.closest("fieldset").hidden; });
      error.hidden = true;
      preview.textContent = summary(values(instance), translate);
    }
    instance.update = update;
    container.addEventListener("change", update);
    container.addEventListener("input", update);
    update();
    return { read: () => read(container) };
  }

  function values(instance) {
    const { controls: c, enabled } = instance;
    return {
      enabled: enabled.checked,
      schedule_config: {
        frequency: c.frequency.value,
        interval: Number(c.interval.value),
        hour: Number(c.hour.value),
        minute: Number(c.minute.value),
        weekdays: c.weekdays.filter(input => input.checked).map(input => Number(input.value)),
        month_days: c.month_days.filter(input => input.checked).map(input => Number(input.value)),
      },
      timezone: c.timezone.value.trim(),
    };
  }

  function read(container) {
    const instance = instances.get(container);
    if (!instance) throw new Error("Schedule editor is not mounted");
    const result = values(instance);
    const c = result.schedule_config;
    function fail(key, control) {
      const message = instance.translate(key);
      instance.error.textContent = message;
      instance.error.hidden = false;
      if (control) control.focus();
      throw new Error(message);
    }
    if (result.enabled) {
      for (const name of ["interval", "hour", "minute"]) {
        const control = instance.controls[name];
        if (!control.closest("label").hidden && (control.value.trim() === "" || !Number.isInteger(Number(control.value)) || Number(control.value) < Number(control.min) || Number(control.value) > Number(control.max))) {
          fail("Enter a whole number within the displayed range.", control);
        }
      }
      if (c.frequency === "weekly" && !c.weekdays.length) fail("Choose at least one day of the week.", instance.controls.weekdays[0]);
      if (c.frequency === "monthly" && !c.month_days.length) fail("Choose at least one day of the month.", instance.controls.month_days[0]);
      try {
        if (!result.timezone) throw new Error();
        new Intl.DateTimeFormat("en", { timeZone: result.timezone }).format();
      } catch (_) { fail("Enter a valid timezone, such as Asia/Jerusalem.", instance.controls.timezone); }
    }
    // Hidden time fields are drafts for another frequency, not part of this cadence.
    if (["minutely", "hourly"].includes(c.frequency)) c.hour = defaults.hour;
    if (c.frequency === "minutely") c.minute = defaults.minute;
    instance.error.hidden = true;
    return result;
  }
  function relocalize(container, translate) {
    const instance = instances.get(container);
    if (!instance) return;
    const draft = values(instance);
    for (const name of ["interval", "hour", "minute"]) draft.schedule_config[name] = instance.controls[name].value;
    mount(container, draft, { translate, editable: instance.editable });
  }
  global.ScheduleEditor = { mount, read, summary, relocalize };
})(window);
