//require.undef('IProfileModule');

define(["jupyter-js-widgets"], function(widget){

    var IProfileView = widget.DOMWidgetView.extend({

        initialize: function(options) {
            this.$el.append('<div id="nav"></div>');
            this.$el.append('<div id="heading"></div>');
            this.$el.append(this.model.get('bokeh_table_div'));
            this.$el.append('<div id="lprofile"></div>');
            this.model.on('change:value_nav', this.value_changed, this);
            this.model.on('change:value_heading', this.value_changed, this);
            this.model.on('change:value_lprofile', this.value_changed, this);
            this.options = options || {};
            this.send("init_complete");
        },

        // Render the view.
        render: function(){
            this.$el.children('#nav').html(this.model.get('value_nav'));
            this.$el.children('#heading').html(this.model.get('value_heading'));
            this.$el.children('#lprofile').html(this.model.get('value_lprofile'));
            this.generate_events();
            return this;
        },

        gen_function_message(index) {
            return function() {this.send("function" + index);};
        },

        gen_nav_message(message) {
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
        },
    });

    return {
        IProfileView: IProfileView
    };
});
