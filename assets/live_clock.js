const timeElement = document.getElementById("local-time");
const timeFormatter = new Intl.DateTimeFormat(navigator.language, {
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
});

function updateLocalTime() {
  timeElement.textContent = timeFormatter.format(new Date());
}

updateLocalTime();
window.setInterval(updateLocalTime, 1000);
