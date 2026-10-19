/* RophysJpeg site configuration.
   Contact form: messages are delivered to rophysjpeg@gmail.com through
   FormSubmit (https://formsubmit.co, free, no account). The very first message
   triggers a one-time "Activate form" email from FormSubmit; click it once and
   every message after that lands in the inbox, with Reply going to the sender.
   To turn delivery off (the form then opens the visitor's email app instead),
   replace the object below with {}. */
window.ROPHYSJPEG_CONFIG = {
  contactForm: {
    enabled: true,
    provider: "formsubmit",
    endpoint: "https://formsubmit.co/ajax/rophysjpeg@gmail.com"
  }
};
