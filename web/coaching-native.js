/* Native documents and explicit assent shared by application and setup pages. */
(function () {
  "use strict";
  var EDGE = "https://coaching-intake.gravelgodcoaching.workers.dev";

  function node(tag, text, parent) {
    var element = document.createElement(tag);
    if (text !== undefined) element.textContent = text;
    if (parent) parent.appendChild(element);
    return element;
  }

  function api(route, values) {
    var controller = new AbortController();
    var timeout = setTimeout(function () { controller.abort(); }, 20000);
    return fetch(EDGE + "/native/" + route, {
      method: "POST", signal: controller.signal,
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(values || {})
    }).then(function (response) {
      return response.json().then(function (data) {
        if (!response.ok) throw new Error(data.error || "Please try again.");
        return data;
      });
    }).finally(function () { clearTimeout(timeout); });
  }

  function saveText(text, filename) {
    var url = URL.createObjectURL(new Blob([text], {type: "text/plain;charset=utf-8"}));
    var link = node("a");
    link.href = url; link.download = filename;
    document.body.appendChild(link); link.click(); link.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  function money(cents) {
    return new Intl.NumberFormat("en-US", {style: "currency", currency: "USD"}).format(cents / 100);
  }

  function serviceText(service) {
    return [service.label + " coaching", money(service.price_cents) + " every " +
      service.billing_period_days + " days", "Setup fee: " + money(service.setup_fee_cents),
      "Requested start: " + (service.desired_start_date || "To be confirmed")]
      .concat(service.services).join("\n");
  }

  function receiptText(receipt) {
    return ["SIGNED COACHING RECORD", "Name: " + receipt.signer_name,
      "Email: " + receipt.signer_email, "Signed: " + receipt.signed_at,
      "Record: " + receipt.receipt_id,
      "Electronic records, coaching agreement, and data consent accepted.",
      serviceText(receipt.service)].concat(receipt.documents.map(function (doc) {
        return "\n" + doc.title + "\nVersion: " + doc.version + "\n" + doc.paragraphs.join("\n\n");
      })).join("\n\n");
  }

  function signedCopy(receipt, parent) {
    var button = node("button", "Download your signed copy", parent);
    button.type = "button";
    button.addEventListener("click", function () {
      saveText(receiptText(receipt), "coaching-signed-record.txt");
    });
    return button;
  }

  function render(container, data) {
    container.replaceChildren();
    container.hidden = false;
    node("h2", "Agreement & Privacy", container);
    node("p", "Review the documents below before signing. You can download a copy to keep.", container);
    var serviceNode = node("div", undefined, container);
    serviceNode.className = "gg-native-service";
    var currentService = data.service || null;
    function setService(service) {
      if (checks && JSON.stringify(currentService) !== JSON.stringify(service)) {
        Object.values(checks).forEach(function (check) { check.checked = false; });
        signature.value = "";
      }
      currentService = service;
      serviceNode.textContent = service ? serviceText(service) : "Select your coaching level above.";
    }
    setService(currentService);
    var hashes = {};
    data.documents.forEach(function (doc) {
      hashes[doc.gate] = doc.sha256;
      var details = node("details", undefined, container);
      node("summary", doc.title, details);
      node("p", "Version " + doc.version, details);
      doc.paragraphs.forEach(function (paragraph) { node("p", paragraph, details); });
    });
    var download = node("button", "Download documents before signing", container);
    download.type = "button";
    download.addEventListener("click", function () {
      saveText((currentService ? serviceText(currentService) + "\n\n" : "") +
        data.documents.map(function (doc) { return doc.paragraphs.join("\n\n"); }).join("\n\n"),
        "coaching-documents.txt");
    });
    var checks = {};
    [
      ["electronic_records", "I consent to electronic records and signatures as described in the agreement."],
      ["coaching_agreement", "I have reviewed and agree to the Coaching Services Agreement, including the risk and health provisions."],
      ["data_consent", "I have reviewed and consent to the processing described in Coaching Privacy + Data Consent."]
    ].forEach(function (choice) {
      var label = node("label", undefined, container);
      label.className = "gg-native-choice";
      var input = node("input", undefined, label);
      input.type = "checkbox"; input.required = true;
      input.id = "native-" + choice[0];
      // No name attribute: the signature is handled once, outside questionnaire data.
      node("span", choice[1], label);
      checks[choice[0]] = input;
    });
    var nameLabel = node("label", "Full legal name for your electronic signature", container);
    nameLabel.htmlFor = "native-signature-name";
    var signature = node("input", undefined, container);
    signature.id = "native-signature-name"; signature.type = "text";
    signature.autocomplete = "name"; signature.required = true;
    node("p", "Typing your name and submitting records your electronic signature. To request a paper or alternate process, email gravelgodcoaching@gmail.com.", container);
    var active = true;
    return {
      setService: setService,
      suspend: function (suspended) {
        active = !suspended; container.hidden = suspended;
        signature.required = !suspended;
        Object.values(checks).forEach(function (check) { check.required = !suspended; });
      },
      acceptance: function () {
        if (!active) return null;
        var result = {signed_name: signature.value, document_hashes: hashes, service: currentService};
        Object.keys(checks).forEach(function (key) { result[key] = checks[key].checked; });
        return result;
      },
      reset: function () {
        signature.value = "";
        Object.values(checks).forEach(function (check) { check.checked = false; });
      }
    };
  }

  function mountIntake(container, form) {
    var controls = null;
    var pending = api("documents").then(function (data) {
      if (!data.enabled) return;
      controls = render(container, data);
      function update() {
        var tier = form.elements.tier.value;
        var base = data.service_options[tier];
        if (base) {
          var service = Object.assign({}, base);
          service.desired_start_date = form.elements.desired_start_date.value;
          controls.setService(service);
        } else controls.setService(null);
        var age = Number(form.elements.age.value);
        controls.suspend(age > 0 && age < 18);
      }
      form.addEventListener("change", update); update();
    }).catch(function () {
      // An unavailable native feature does not discard an otherwise valid application.
    });
    return {
      ready: pending,
      acceptance: function () { return controls ? controls.acceptance() : null; },
      showReceipt: function (receipt) {
        if (!receipt) return;
        if (controls) controls.reset();
        signedCopy(receipt, container);
      }
    };
  }

  function mountSetup(container, status) {
    container.replaceChildren(); container.hidden = true;
    var token = window.__GGSetupToken || new URLSearchParams(location.hash.slice(1)).get("token") || "";
    delete window.__GGSetupToken;
    // The capability stays in memory after it is removed from the visible URL.
    history.replaceState(null, "", location.pathname);
    function message(text) { status.textContent = text; }
    if (!token) { message("Open the private setup link from your coach."); return; }
    message("Loading your coaching setup...");
    api("setup", {token: token}).then(function (data) {
      if (!data.enabled) { message("Please contact gravelgodcoaching@gmail.com to finish setup."); return; }
      message(data.name + ", finish your coaching setup below.");
      var currentHashes = {};
      data.documents.forEach(function (doc) { currentHashes[doc.gate] = doc.sha256; });
      var currentReceipt = data.receipts.some(function (receipt) {
        var receiptHashes = {};
        receipt.documents.forEach(function (doc) { receiptHashes[doc.gate] = doc.sha256; });
        return JSON.stringify(receiptHashes) === JSON.stringify(currentHashes) &&
          Object.keys(data.service).every(function (key) {
            return JSON.stringify(receipt.service[key]) === JSON.stringify(data.service[key]);
          });
      });
      if (currentReceipt) {
        container.hidden = false;
        node("p", "Your signed records are saved.", container);
        data.receipts.forEach(function (receipt) { signedCopy(receipt, container); });
        return;
      }
      var form = node("form", undefined, container);
      var inner = node("div", undefined, form);
      var controls = render(inner, data);
      var submit = node("button", "Sign and save", form); submit.type = "submit";
      container.hidden = false;
      form.addEventListener("submit", function (event) {
        event.preventDefault();
        if (!form.reportValidity()) return;
        submit.disabled = true;
        api("accept", {token: token, acceptance: controls.acceptance()}).then(function (result) {
          form.replaceChildren();
          node("p", "Your agreement and privacy consent are signed and saved.", form);
          signedCopy(result.receipt, form);
          message("Setup documents complete. Your coach will send the remaining next steps.");
        }).catch(function (error) { message(error.message); submit.disabled = false; });
      });
    }).catch(function (error) { message(error.message); });
  }

  window.GGNativeOnboarding = {mountIntake: mountIntake, mountSetup: mountSetup,
    receiptText: receiptText};
}());
