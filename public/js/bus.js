// Event-driven client: a tiny publish/subscribe bus. UI code emits events, other code reacts.
const bus = {
  handlers: {},
  on(name, fn) { (this.handlers[name] = this.handlers[name] || []).push(fn); },
  emit(name, data) { (this.handlers[name] || []).forEach(fn => fn(data)); },
};
