var widgets = require('jupyter-js-widgets');

var IProfileView = widgets.DOMWidgetView.extend({
  initialize: function(options) {
    this.listenTo(this.model, 'sync change', this.render);
    this.model.fetch();
    this.render();
    this.$el.append('<div id="iprofile-nav"></div>');
    this.$el.append('<div id="heading"></div>');
    this.$el.append(this.model.get('bokeh_table_div'));
    this.$el.append('<div id="lprofile"></div>');
    this.options = options || {};
    this.send("init_complete");
  },

  // Render the view.
  render: function(){
    this.$('#iprofile-nav').html(this.nav_html());
    this.$el.children('#heading').html(this.model.get('value_heading'));
    this.$el.children('#lprofile').html(this.model.get('value_lprofile'));
    this.generate_events();
    return this;
  },

  nav_html: function(){
    var html_home = '<img src="' + require('./home.svg') + '">';

    // If home button is 'active' then wrap in an <a> tag.
    if (this.model.get('nav_home_active')) {
      html_home = '<a id="iprofile_home" style="cursor: pointer;">' +
                  html_home + '</a>';
    }

    if (this.model.get('nav_back_active')) {
      var html_back = '<a id="iprofile_back" style="cursor: pointer;">' +
                      '<img src="' + require('./back.svg') + '"></a>';
    } else {
      var html_back = '<img src="' + require('./back_grey.svg') + '">';
    }

    if (this.model.get('nav_forward_active')) {
      var html_forward = '<a id="iprofile_forward" style="cursor: pointer;">' +
                         '<img src="' + require('./forward.svg') + '"></a>';
    } else {
      var html_forward = '<img src="' + require('./forward_grey.svg') + '">';
    }

    return (html_home + html_back + html_forward);
  },

  gen_function_message: function(index) {
    return function() {this.send("function" + index);};
  },

  gen_nav_message: function(message) {
    return function() {this.send(message);};
  },

  generate_events: function(){
    // Generate click events for function table.
    var events = {};
    events["click #iprofile_home"] = this.gen_nav_message("home");
    events["click #iprofile_back"] = this.gen_nav_message("back");
    events["click #iprofile_forward"] = this.gen_nav_message("forward");

    for (var index = 0;  index < this.model.get('n_table_elements'); index++) {
        events["click #function" + index] = this.gen_function_message(index);
    }
    this.events = events;
    this.delegateEvents();
  },

  events: {},

  value_changed: function() {
      this.render();
  }
});

module.exports = {
    IProfileView: IProfileView
};
