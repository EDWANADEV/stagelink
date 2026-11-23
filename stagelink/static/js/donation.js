(() => {
  const form = document.getElementById("donation-form");
  if (!form) return;

  const amountInput = document.getElementById("donation-amount");
  const summary = document.getElementById("donation-summary");
  const errorBox = document.getElementById("donation-error");
  const progress = document.getElementById("donation-progress");
  const submit = document.getElementById("donation-submit");
  const donorDetails = document.getElementById("donor-details");
  const emailInput = document.getElementById("donor-email");
  const mobileDetails = document.getElementById("mobile-money-details");
  const phoneInput = document.getElementById("donor-phone");
  const networkInput = document.getElementById("donor-network");
  const amountFormatter = new Intl.NumberFormat(document.documentElement.lang || "fr-FR");
  let idempotencyKey = crypto.randomUUID();

  const selectedOption = () => form.querySelector('input[name="payment_option"]:checked');
  const selectedData = () => {
    const option = selectedOption();
    return option ? { provider: option.dataset.provider, method: option.dataset.method } : null;
  };

  const updateForm = () => {
    const selected = selectedData();
    const amount = Number(amountInput.value);
    document.querySelectorAll(".donation-preset").forEach((button) => {
      const active = button.dataset.amount === amountInput.value;
      button.classList.toggle("border-primary", active);
      button.classList.toggle("text-primary", active);
      button.setAttribute("aria-pressed", String(active));
    });
    donorDetails.classList.toggle("hidden", !selected || selected.provider === "stripe");
    mobileDetails.classList.toggle(
      "hidden",
      !selected || selected.provider !== "flutterwave" || selected.method !== "mobile_money",
    );
    emailInput.required = Boolean(selected && selected.provider === "flutterwave");
    phoneInput.required = Boolean(selected && selected.method === "mobile_money");
    networkInput.required = Boolean(selected && selected.method === "mobile_money");

    if (Number.isInteger(amount) && amount > 0 && selected) {
      const label = selectedOption().parentElement.querySelector("span").textContent.trim();
      summary.textContent = `${amountFormatter.format(amount)} XAF · ${label}`;
    } else {
      summary.textContent = "";
    }
  };

  const showError = (message) => {
    errorBox.textContent = message;
    errorBox.classList.remove("hidden");
    progress.classList.add("hidden");
    submit.disabled = false;
    form.removeAttribute("aria-busy");
    form.querySelectorAll("input, select, .donation-preset").forEach((control) => {
      control.disabled = false;
    });
  };

  document.querySelectorAll(".donation-preset").forEach((button) => {
    button.addEventListener("click", () => {
      amountInput.value = button.dataset.amount;
      updateForm();
    });
  });
  amountInput.addEventListener("input", updateForm);
  form.querySelectorAll('input[name="payment_option"]').forEach((input) => {
    input.addEventListener("change", updateForm);
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    errorBox.classList.add("hidden");
    const selected = selectedData();
    const amount = Number(amountInput.value);
    if (!form.reportValidity()) return;
    if (!selected || !Number.isInteger(amount) || amount < 1 || amount > 9999999999) {
      showError(form.dataset.amountError);
      return;
    }
    submit.disabled = true;
    form.setAttribute("aria-busy", "true");
    form.querySelectorAll("input, select, .donation-preset").forEach((control) => {
      control.disabled = true;
    });
    progress.textContent = form.dataset.confirming;
    progress.classList.remove("hidden");
    const payload = {
      amount: String(amount),
      ...selected,
      email: emailInput.value,
      phone_number: phoneInput.value,
      network: networkInput.value,
    };

    try {
      const response = await fetch(form.dataset.createUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": form.querySelector('[name="csrfmiddlewaretoken"]').value,
          "Idempotency-Key": idempotencyKey,
        },
        body: JSON.stringify(payload),
      });
      let result;
      try {
        result = await response.json();
      } catch (_error) {
        throw new SyntaxError(form.dataset.paymentError);
      }
      if (!response.ok) {
        const fieldError = result.errors?.amount?.[0]?.message;
        throw new Error(fieldError || result.error || form.dataset.paymentError);
      }

      if (result.checkout_url) {
        const checkout = new URL(result.checkout_url);
        if (checkout.protocol !== "https:") throw new Error(form.dataset.paymentError);
        if (
          selected.provider === "stripe" &&
          checkout.hostname !== "checkout.stripe.com"
        ) {
          throw new Error(form.dataset.paymentError);
        }
        window.location.assign(checkout.href);
        return;
      }

      const returnUrl = new URL(form.dataset.returnUrl, window.location.origin);
      returnUrl.searchParams.set("payment_id", result.payment_id);
      window.location.assign(returnUrl.href);
    } catch (error) {
      const isNetworkOrResponseError =
        error instanceof TypeError || error instanceof SyntaxError;
      showError(
        isNetworkOrResponseError
          ? form.dataset.paymentError
          : error.message || form.dataset.paymentError,
      );
    }
  });

  updateForm();
})();
