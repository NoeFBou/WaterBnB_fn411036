//
// Scripts Noe Florence
// 

//fonction for the navbar
window.addEventListener('DOMContentLoaded', event => {

    // Navbar shrink function
    var navbarShrink = function () {
        const navbarCollapsible = document.body.querySelector('#mainNav');
        if (!navbarCollapsible) {
            return;
        }
        if (window.scrollY === 0) {
            navbarCollapsible.classList.remove('navbar-shrink')
        } else {
            navbarCollapsible.classList.add('navbar-shrink')
        }

    };

    // Shrink the navbar 
    navbarShrink();

    // Shrink the navbar when page is scrolled
    document.addEventListener('scroll', navbarShrink);

    // Activate Bootstrap scrollspy on the main nav element
    const mainNav = document.body.querySelector('#mainNav');
    if (mainNav) {
        new bootstrap.ScrollSpy(document.body, {
            target: '#mainNav',
            rootMargin: '0px 0px -40%',
        });
    };

    // Collapse responsive navbar when toggler is visible
    const navbarToggler = document.body.querySelector('.navbar-toggler');
    const responsiveNavItems = [].slice.call(
        document.querySelectorAll('#navbarResponsive .nav-link')
    );
    responsiveNavItems.map(function (responsiveNavItem) {
        responsiveNavItem.addEventListener('click', () => {
            if (window.getComputedStyle(navbarToggler).display !== 'none') {
                navbarToggler.click();
            }
        });
    });

});

function startUpdate(){
  setInterval(function () {
	  fetch("value?temperature&light&fanSpeed&cooler&regulation&heater&fire&esptime")
	  // fetch() returns a promise. When we have received a response from the server,
	  // the promise's `then()` handler is called with the response.
	  .then( function (response) {
		  // Our handler throws an error if the request did not succeed.
		  if (!response.ok) {
		    throw new Error(`HTTP error: ${response.status}`);
		  }

		  return response.json();
	  })
	  .then(function (text){
		  if (text.temperature !== undefined)
              document.getElementById("temperature").innerHTML = text.temperature+"°C";
          if (text.light !== undefined)
              document.getElementById("light").innerHTML = text.light +" Lumen";
          if (text.fanSpeed !== undefined)
              document.getElementById("fanSpeed").innerHTML = text.fanSpeed;
          if (text.coolerState !== undefined)
              document.getElementById("coolerState").innerHTML = text.coolerState;
          if (text.regulationState !== undefined)
              document.getElementById("regulationState").innerHTML = (text.regulationState) ? "active" : "desactive";
          if (text.heaterState !== undefined)
              document.getElementById("heaterState").innerHTML = text.heaterState;
          if (text.fire !== undefined)
              document.getElementById("fire").innerHTML = (text.fire) ? "Detected" : "not Detected";
          if (text.esptime !== undefined)
              document.getElementById("currentTime").innerHTML = "Uptime :" + text.esptime;

      })

	  .catch(function (error){
		  console.log(error);		
	  });
  }, 2000);
}
  
document.addEventListener('DOMContentLoaded', function() {
startUpdate();
});
