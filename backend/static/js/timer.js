let qrImg = document.getElementById("qrImage");
let timer = document.getElementById("timer");

function updateQR() {
    qrImg.src = qrImg.src.split("?")[0] + "?t=" + new Date().getTime();  // Forces refresh
    timer.innerText = "QR refreshed at: " + new Date().toLocaleTimeString();
}

setInterval(updateQR, 60000);  // Refresh every 60 sec
updateQR();  // Initial refresh