$(document).ready(function() {
    // Start refreshing the page as soon as we're loaded
    //kakumonster.ask();

    // Initialize the chat text input to send contents when enter pressed
    $("#chatInput").keypress(function(e) {
        if (e.keyCode == 13) {
          kakumonster.sendChat();
        }
      });
    $("#askKakumonster").click(function() { kakumonster.ask(); });
    $("#kakumonster").animate({opacity: "0"}, "fast").slideUp("fast");
  });

$(window).unload(function() {
    // When we leave the page, notify the server
    //kakumonster.leaving=true;
    //kakumonster.leave();
  });


var kakumonster = {
  /*
  forceRefresh: function() {
    // If there's not already a refresh in process, refresh immediately.
    if (kakumonster.refreshTimer) {
      // There's a timer, which means there's no refresh in process, so
      // fire off the refresh - this will stop the existing timer so we don't
      // get a double update.
      kakumonster.refresh();
    }
  },*/

  // Calls the server to get the next suggestion
  ask: function() {
    // Stop any existing timer
    //if (kakumonster.refreshTimer) {
      //window.clearTimeout(kakumonster.refreshTimer);
      //delete kakumonster.refreshTimer;
    //}
    // Turn on to display busy cursor during ajax calls for debugging
    // $(".busy").show();
    var options = {
      url: "/kakumonster/", // + blitz.user_email + "/" + lobby.msgId,
      // Add random param to URL to avoid browser caching of HTTP GETs
      //data: {z: new Date().getTime()},
      data: {z: "HELLO"},
      dataType: "json",
      error: kakumonster.fail,
      success: kakumonster.handleAjaxResponse
    };
    $.ajax(options);
  },

  // Error handler for ajax requests
  fail: function (xhr, textStatus, errorThrown) {
    if (xhr.status == 410) {
      // Whatever entity we are trying to access has been deleted
      alert("Sorry, this game has been deleted.");
      //blitz.clickHandlers.enterLobby();
      return;
    }
    // Just try sending the request again - if the server is down, this can
    // lead to an infinite loop, so we put in a delay and try it every few
    // seconds.
    alert('Failure - Trying again!');
    //var ajaxOptions = this;
    //window.setTimeout(function() { $.ajax(ajaxOptions);}, 2*1000);
  },

  handleAjaxResponse: function(data) {
    // We got our response - make sure the busy cursor is off
    $(".busy").hide();
    var mistakes = data.mistakes;
    var maybes = data.maybes;

    var mistakesText = mistakes.join("<br/>");
    var maybesText = maybes.join("<br/>");

    $(".mistakes").html(mistakesText);
    $(".maybes").html(maybesText);

    $("#kakumonster").slideDown("slow").animate({opacity: "1"}, "slow");

    // Convert the player name array to a list we can display
    //kakumonster.updatePlayerList(data.player_list);

    // Refresh the data every 5 secs
    //kakumonster.refreshTimer = window.setTimeout(lobby.refresh, 5*1000);
  },

/*
  updateGameList: function(gameList) {
    // Generate content of game table based on what was sent to us
    content = "";
    jQuery.each(gameList, function(index, game) {
        content += "<tr><td>" + game.creator + "</td><td>" +
          (game.opponent ? game.opponent : "&nbsp;") + "</td><td>" +
          (game.time_limit ?  (game.time_limit + " min") : "untimed") +
           "</td><td>";
        // OK, figure out what actions we have on this game. Choices are:
        // 1) Delete - if is_participant && opponent = null
        // 2) Join - if !is_participant && opponent = null
        // 3) Watch - if !is_participant && opponent = null
        //
        // We also check to see if the user is an invitee or if he's a
        // participant in an active blitz game, in which case we prompt him to
        // enter the game immediately.
        action = [];
        if (game.is_participant || game.is_invitee) {
          // Haven't prompted about this game before
          if (game.is_invitee) {
            // Display an invite dialog (after setting the flag so we don't
            // prompt about this game again)
            if (!lobby.ignoreMap[game.key] && !blitz.dialogActive()) {
              lobby.ignoreMap[game.key] = true;
              lobby.displayJoinDialog(game.creator, game.key);
            }
            action.push({id: "joinGame", label: "Join"});
          } else {
            // If the user is a participant in an active blitz game, warn
            // them and let them enter.
            if (!lobby.ignoreMap[game.key] && !blitz.dialogActive() &&
                game.status == lobby.GAME_STATUS_ACTIVE && game.time_limit) {
              // Don't prompt about this game again.
              lobby.ignoreMap[game.key] = true;
              lobby.displayEnterDialog(game.is_creator ?
                                       game.opponent : game.creator, game.key);
            }
            if (game.status == lobby.GAME_STATUS_ACTIVE) {
              action.push({id: "goGame", label: "Go"});
            }
          }
          if (game.can_delete) {
            action.push({id: "deleteGame", label: "Delete"});
          }
        } else if (game.status == lobby.GAME_STATUS_ACTIVE) {
          // Not a participant, and the game is full - action = watch
          action.push({id: "goGame", label: "Watch"});
        } else {
          // Not a participant, and there's no opponent yet - action = Join
          action.push({id: "joinGame", label: "Join"});
        }
        if (action.length == 0) {
          content += "&nbsp;";
        } else {
          jQuery.each(action, function(index, item) {
              if (index > 0) {
                content += "&nbsp;";
              }
              content += '<a class="btn" href="#" key="' + game.key +
                '" id="' + item.id + '">' + item.label + "</a>";
            });
        }
        content += "</td></tr>";
      });
    // Remove the old games, replace with new content
    $(".gameTable tr:not(.gameTableHeader)").remove();
    if (content.length) {
      $(".gameTable").append(content);
    }

    // Setup click handlers for the newly added buttons.
    $(".gameTable a").click(function(args) {
        var key = this.getAttribute('key');
        var func = lobby[this.id];
        func(key);
      });

    // Add stripes to the table
    $(".gameTable tr:even").addClass("even");
    $(".gameTable tr:odd").addClass("odd");
  },

  displayJoinDialog: function(creator, key) {
    $('#inviter').text(creator);
    $('#joinGame').attr({key: key});
    blitz.initAndDisplayDialog("#joinDialog");
  },

  displayEnterDialog: function(opponent, key) {
    $('#blitzOpponent').text(opponent);
    $('#goGame').attr({key: key});
    blitz.initAndDisplayDialog("#enterDialog");
    $('#goGame').attr({ref: key});
  },

  goGame: function(gameKey) {
    blitz.clickHandlers.goGame(gameKey);
  },

  joinGame: function(gameKey) {
    var options = {
      url: "/game_ajax/" + gameKey + "/join",
      // We don't actually need to send the key up (since it's already in
      // the URL) but some proxies don't like having a zero-length body for
      // POSTs so we need to put something in there.
      data: {gameKey: gameKey},
      type: "POST",
      success: function() {lobby.goGame(gameKey); },
      error: function() {
        alert("Could not join game");
        lobby.forceRefresh();
      }
    }
    $.ajax(options);
  },

  // Given the key to a game, delete it
  deleteGame: function(gameKey) {
    $(".busy").show();
    var options = {
      url: "/game_ajax/" + gameKey,
      type: "DELETE",
      success: lobby.forceRefresh
    };
    $.ajax(options);
  },
*/
};
