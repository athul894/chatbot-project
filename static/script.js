async function sendMessage() {
    let input = document.getElementById("userInput");
    let message = input.value;

    if (message.trim() === "") return;

    let chatbox = document.getElementById("chatbox");

    chatbox.innerHTML += `<p><b>You:</b> ${message}</p>`;

    let response = await fetch("/get", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ message: message })
    });

    let data = await response.json();

    chatbox.innerHTML += `<p style="color:green;"><b>Bot:</b> ${data.response}</p>`;

    input.value = "";
}