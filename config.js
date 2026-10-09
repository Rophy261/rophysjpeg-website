/* =====================================================================
   RophysJpeg site configuration — edit this file, then redeploy.
   (The build never overwrites site/config.js once it exists.)
   ===================================================================== */
window.ROPHYSJPEG_CONFIG = {

  /* CONTACT FORM DELIVERY
     The old Format form backend was cancelled with the subscription, so the
     form ships switched OFF: the Send Message button is disabled and visitors
     see a notice. Nothing is sent and no fake success message is ever shown.

     To switch it on:
       1. Create a form with a delivery service, for example
            - Formspree  (https://formspree.io)  -> endpoint looks like https://formspree.io/f/abcdwxyz
            - Web3Forms  (https://web3forms.com) -> endpoint https://api.web3forms.com/submit + access key
            - your own HTTPS endpoint that accepts a POST of FormData and returns 2xx
          and point it at the inbox where you want messages.
       2. Fill in provider, endpoint (and accessKey for Web3Forms) below.
       3. Put the inbox address you verified with that service in "recipient".
          It is only used here to confirm the form is configured; it is not
          printed on the page and the service decides where mail goes.
       4. Set enabled: true, save, redeploy, then send yourself a test message.
  */
  contactForm: {
    enabled: false,
    provider: "formspree",   // "formspree" | "web3forms" | "custom"
    endpoint: "",            // https://...
    accessKey: "",           // Web3Forms only
    recipient: "",           // e.g. the address you verified with the service
    subject: "New message from rophysjpeg.com",
    successMessage: "Thank you. Your message has been sent.",
    errorMessage: "Sorry, your message could not be sent. Please try again later or reach out on Instagram or LinkedIn.",
    unavailableMessage: "Message delivery has not been set up for this website yet, so this form cannot send messages. Please reach out on Instagram or LinkedIn in the meantime."
  },

  /* INSTAGRAM FEED (About page)
     Instagram no longer allows a website to read a feed without an authorised
     connection, so the feed comes through Behold (https://behold.so, free plan:
     1 feed, 6 posts, refreshed daily, 1,200 views a month).
       1. Sign in at behold.so, connect the @rophysjpeg Instagram account
          (it must be a Professional - Creator or Business - account).
       2. Create a feed and copy its JSON feed URL (https://feeds.behold.so/...).
       3. Paste it below, set enabled: true and redeploy.
     If the feed is off, empty or over its monthly limit, the About page simply
     shows the "View @rophysjpeg on Instagram" link instead. */
  instagramFeed: {
    enabled: false,
    feedUrl: "",
    count: 6
  }
};
