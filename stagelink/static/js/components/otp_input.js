document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-otp-input]").forEach((container) => {
        const inputs = [
            ...container.querySelectorAll("[data-otp-digit]"),
        ];
        const hiddenInput = container.querySelector(
            'input[type="hidden"]',
        );

        if (!hiddenInput || inputs.length === 0) {
            return;
        }

        const updateValue = () => {
            hiddenInput.value = inputs.map((input) => input.value).join("");
        };

        inputs.forEach((input, index) => {
            input.addEventListener("input", (event) => {
                const value = event.target.value.replace(/\D/g, "");

                event.target.value = value.slice(-1);

                if (event.target.value && index < inputs.length - 1) {
                    inputs[index + 1].focus();
                }

                updateValue();
            });

            input.addEventListener("keydown", (event) => {
                if (
                    event.key === "Backspace" &&
                    !input.value &&
                    index > 0
                ) {
                    inputs[index - 1].focus();
                }
            });

            input.addEventListener("paste", (event) => {
                event.preventDefault();

                const pasted = event.clipboardData
                    .getData("text")
                    .replace(/\D/g, "")
                    .slice(0, inputs.length);

                pasted.split("").forEach((digit, digitIndex) => {
                    inputs[digitIndex].value = digit;
                });

                updateValue();

                const nextIndex = Math.min(
                    pasted.length,
                    inputs.length - 1,
                );

                inputs[nextIndex].focus();
            });
        });
    });
});