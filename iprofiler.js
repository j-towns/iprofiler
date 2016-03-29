require(["nbextensions/widgets/widgets/js/widget", "nbextensions/widgets/widgets/js/manager"], function(widget, manager){

    var IProfileView = widget.DOMWidgetView.extend({

        // Render the view.
        render: function(){
            this.$el.html(this.model.get('value'));
            this.model.on('change:value', this.value_changed, this);
            this.generate_events();
        },

        gen_function_message(index) {
            return function() {this.send("function" + index);};
        },

        generate_events: function(){
            // Generate click events for function table.
            var events = {};
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

    manager.WidgetManager.register_widget_view('IProfileView', IProfileView);
});
