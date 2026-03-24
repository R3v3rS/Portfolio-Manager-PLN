(function ($, window) {
    'use strict';

    var chartUid = 0;

    function formatValue(value, unit) {
        if (value === null || value === undefined || value === '') {
            return '-';
        }
        var num = typeof value === 'number' ? value : parseFloat(value);
        if (isNaN(num)) {
            return value;
        }
        if (unit === '%') {
            return num.toFixed(2) + unit;
        }
        return num.toFixed(2) + (unit || '');
    }

    function disposeChart($el) {
        var chart = $el.data('mfChartInstance');
        var resizeHandler = $el.data('mfChartResize');
        var zoomHandler = $el.data('mfChartZoom');
        var rangeControls = $el.data('mfChartRangeButtons');
        if (resizeHandler) {
            window.removeEventListener('resize', resizeHandler);
            $el.removeData('mfChartResize');
        }
        if (chart && zoomHandler) {
            chart.off('dataZoom', zoomHandler);
            $el.removeData('mfChartZoom');
        }
        if (rangeControls && rangeControls.container) {
            rangeControls.container.remove();
        }
        $el.removeData('mfChartRangeButtons');
        $el.removeData('mfChartPendingRange');
        if (chart) {
            chart.dispose();
            $el.removeData('mfChartInstance');
        }
    }

    function buildSeries(series, unit) {
        return (series || []).map(function (serie) {
            var dataPoints = (serie.data || []).map(function (point) {
                if ($.isArray(point) && point.length >= 2) {
                    var value = typeof point[1] === 'number' ? point[1] : parseFloat(point[1]);
                    return [point[0], value];
                }
                return point;
            });

            var seriesType = (serie.type || '').toLowerCase();
            if (seriesType !== 'bar' && seriesType !== 'line') {
                seriesType = 'line';
            }

            var config = {
                type: seriesType,
                name: serie.name || 'Seria',
                data: dataPoints,
                emphasis: { focus: 'series' }
            };

            if (seriesType === 'line') {
                config.smooth = false;
                config.showSymbol = false;
                config.lineStyle = { width: 2 };

                if (serie.area) {
                    config.areaStyle = { opacity: 0.2 };
                }
            }

            if (serie.markPoints) {
                config.markPoint = { data: serie.markPoints };
            }

            if (serie.markLines) {
                config.markLine = { data: serie.markLines };
            }

            return config;
        });
    }

    function cloneSeriesData(series) {
        return (series || []).map(function (serie) {
            return (serie.data || []).map(function (point) {
                if ($.isArray(point)) {
                    return [point[0], point[1]];
                }
                return point;
            });
        });
    }

    function toNumeric(value) {
        if (value === null || value === undefined || value === '') {
            return null;
        }
        if (typeof value === 'number') {
            return isFinite(value) ? value : null;
        }
        var num = parseFloat(value);
        return isNaN(num) ? null : num;
    }

    function normalizeAxisValue(value, fallback) {
        if (value instanceof Date) {
            return value.getTime();
        }
        if (typeof value === 'number') {
            return value;
        }
        if (typeof value === 'string') {
            var parsedDate = Date.parse(value);
            if (!isNaN(parsedDate)) {
                return parsedDate;
            }
            var parsedNum = parseFloat(value);
            if (!isNaN(parsedNum)) {
                return parsedNum;
            }
        }
        return typeof fallback === 'number' ? fallback : null;
    }

    function getAxisRawValue(point, index) {
        if ($.isArray(point)) {
            return point[0];
        }
        return index;
    }

    function getAxisComparableValue(point, index) {
        return normalizeAxisValue(getAxisRawValue(point, index), index);
    }

    function getPointNumericValue(point) {
        if ($.isArray(point)) {
            return toNumeric(point[1]);
        }
        return toNumeric(point);
    }

    function computeStartAxisValue(zoom, firstSeries) {
        if (!zoom) {
            return null;
        }
        if (zoom.startValue !== undefined) {
            return zoom.startValue;
        }
        if (!firstSeries || !firstSeries.length || zoom.start === undefined) {
            return null;
        }
        var targetIndex = Math.floor(firstSeries.length * (zoom.start / 100));
        if (targetIndex < 0) {
            targetIndex = 0;
        }
        if (targetIndex >= firstSeries.length) {
            targetIndex = firstSeries.length - 1;
        }
        var targetPoint = firstSeries[targetIndex];
        return $.isArray(targetPoint) ? targetPoint[0] : targetIndex;
    }

    function isFullRangeZoom(zoom, seriesData) {
        if (!zoom) {
            return true;
        }
        var hasExplicitValues = zoom.startValue !== undefined || zoom.endValue !== undefined;
        var fullByPercent = (zoom.start === undefined || zoom.start <= 0) && (zoom.end === undefined || zoom.end >= 100);
        if (!hasExplicitValues) {
            return fullByPercent;
        }
        if (!seriesData || !seriesData.length) {
            return fullByPercent;
        }
        var firstPoint = seriesData[0];
        var lastPoint = seriesData[seriesData.length - 1];
        var firstComparable = getAxisComparableValue(firstPoint, 0);
        var lastComparable = getAxisComparableValue(lastPoint, seriesData.length - 1);
        var startComparable = normalizeAxisValue(zoom.startValue, null);
        var endComparable = normalizeAxisValue(zoom.endValue, null);
        if (startComparable === null || endComparable === null) {
            return fullByPercent;
        }
        return startComparable <= firstComparable && endComparable >= lastComparable;
    }

    function buildRebasedSeriesData(originalSeriesData, startAxisValue, rebaseMode) {
        var normalizedStart = startAxisValue !== null && startAxisValue !== undefined ? normalizeAxisValue(startAxisValue, null) : null;

        return originalSeriesData.map(function (serieData) {
            var baseValue = null;

            if (normalizedStart !== null) {
                for (var i = 0; i < serieData.length; i++) {
                    var point = serieData[i];
                    var numericValue = getPointNumericValue(point);
                    if (numericValue === null) {
                        continue;
                    }
                    var axisComparable = getAxisComparableValue(point, i);
                    if (axisComparable !== null && axisComparable >= normalizedStart) {
                        baseValue = numericValue;
                        break;
                    }
                }
            }

            if (baseValue === null) {
                for (var j = 0; j < serieData.length; j++) {
                    var candidate = getPointNumericValue(serieData[j]);
                    if (candidate !== null) {
                        baseValue = candidate;
                        break;
                    }
                }
            }

            if (baseValue === null) {
                baseValue = 0;
            }

            return serieData.map(function (point) {
                if ($.isArray(point)) {
                    var pointNumeric = getPointNumericValue(point);
                    if (pointNumeric === null) {
                        return [point[0], point[1]];
                    }
                    if (rebaseMode && baseValue !== 0) {
                        // Raw prices ‚?? percentage: ((current / base) - 1) * 100
                        return [point[0], ((pointNumeric / baseValue) - 1) * 100];
                    }
                    return [point[0], pointNumeric - baseValue];
                }
                var standaloneNumeric = getPointNumericValue(point);
                if (standaloneNumeric === null) {
                    return point;
                }
                if (rebaseMode && baseValue !== 0) {
                    return ((standaloneNumeric / baseValue) - 1) * 100;
                }
                return standaloneNumeric - baseValue;
            });
        });
    }

    function buildAxisInfo(seriesData) {
        if (!seriesData || !seriesData.length) {
            return null;
        }

        var points = [];
        for (var i = 0; i < seriesData.length; i++) {
            var point = seriesData[i];
            var rawValue = getAxisRawValue(point, i);
            var comparableValue = getAxisComparableValue(point, i);
            if (comparableValue === null) {
                continue;
            }
            points.push({ raw: rawValue, comparable: comparableValue });
        }

        if (!points.length) {
            return null;
        }

        points.sort(function (a, b) {
            return a.comparable - b.comparable;
        });

        return {
            points: points,
            min: points[0],
            max: points[points.length - 1]
        };
    }

    function clampAxisPoint(axisInfo, targetComparable, preferStart) {
        if (!axisInfo || !axisInfo.points.length) {
            return null;
        }

        var points = axisInfo.points;
        if (preferStart) {
            if (targetComparable === null || targetComparable === undefined || isNaN(targetComparable)) {
                return axisInfo.min;
            }
            if (targetComparable <= axisInfo.min.comparable) {
                return axisInfo.min;
            }
            for (var i = 0; i < points.length; i++) {
                if (points[i].comparable >= targetComparable) {
                    return points[i];
                }
            }
            return axisInfo.max;
        }

        if (targetComparable === null || targetComparable === undefined || isNaN(targetComparable)) {
            return axisInfo.max;
        }
        if (targetComparable >= axisInfo.max.comparable) {
            return axisInfo.max;
        }
        for (var j = points.length - 1; j >= 0; j--) {
            if (points[j].comparable <= targetComparable) {
                return points[j];
            }
        }
        return axisInfo.min;
    }

    function shiftDateByMonths(date, months) {
        var shifted = new Date(date.getTime());
        var desiredDay = shifted.getDate();
        shifted.setDate(1);
        shifted.setMonth(shifted.getMonth() + months);
        var lastDay = new Date(shifted.getFullYear(), shifted.getMonth() + 1, 0).getDate();
        shifted.setDate(Math.min(desiredDay, lastDay));
        return shifted;
    }

    function shiftDateByYears(date, years) {
        return shiftDateByMonths(date, years * 12);
    }

    function buildComparableRange(startComparable, endComparable, axisInfo) {
        if (!axisInfo) {
            return null;
        }

        var startPoint = clampAxisPoint(axisInfo, startComparable, true);
        var endPoint = clampAxisPoint(axisInfo, endComparable, false);
        if (!startPoint || !endPoint) {
            return null;
        }
        if (startPoint.comparable > endPoint.comparable) {
            startPoint = axisInfo.min;
        }
        return {
            startValue: startPoint.raw,
            endValue: endPoint.raw
        };
    }

    function setupRangeControls($el, chart, originalSeriesData) {
        if (!$el || !$el.length) {
            return;
        }

        var existing = $el.data('mfChartRangeButtons');
        if (existing && existing.container) {
            existing.container.remove();
        }
        $el.removeData('mfChartRangeButtons');
        $el.removeData('mfChartPendingRange');

        var firstSeries = originalSeriesData && originalSeriesData.length ? originalSeriesData[0] : null;
        var axisInfo = buildAxisInfo(firstSeries);
        if (!axisInfo) {
            return;
        }

        var $container = $('<div/>').addClass('fund-chart-range-controls text-right');
        var $group = $('<div/>').addClass('btn-group btn-group-sm').attr('role', 'group');
        $container.append($group);

        var rangeData = {
            container: $container,
            buttons: [],
            setActive: function (key) {
                for (var i = 0; i < rangeData.buttons.length; i++) {
                    var button = rangeData.buttons[i];
                    if (key && button.key === key) {
                        button.$el.removeClass('btn-default').addClass('btn-primary');
                    } else {
                        button.$el.removeClass('btn-primary').addClass('btn-default');
                    }
                }
            }
        };

        var rangeConfigs = [
            {
                key: 'ytd',
                label: 'YTD',
                calc: function () {
                    var endComparable = axisInfo.max.comparable;
                    var endDate = new Date(endComparable);
                    var startComparable = new Date(endDate.getFullYear(), 0, 1).getTime();
                    return buildComparableRange(startComparable, endComparable, axisInfo);
                }
            },
            {
                key: '1m',
                label: '1m',
                calc: function () {
                    var endComparable = axisInfo.max.comparable;
                    var startComparable = shiftDateByMonths(new Date(endComparable), -1).getTime();
                    return buildComparableRange(startComparable, endComparable, axisInfo);
                }
            },
            {
                key: '3m',
                label: '3m',
                calc: function () {
                    var endComparable = axisInfo.max.comparable;
                    var startComparable = shiftDateByMonths(new Date(endComparable), -3).getTime();
                    return buildComparableRange(startComparable, endComparable, axisInfo);
                }
            },
            {
                key: '6m',
                label: '6m',
                calc: function () {
                    var endComparable = axisInfo.max.comparable;
                    var startComparable = shiftDateByMonths(new Date(endComparable), -6).getTime();
                    return buildComparableRange(startComparable, endComparable, axisInfo);
                }
            },
            {
                key: '1r',
                label: '1r',
                calc: function () {
                    var endComparable = axisInfo.max.comparable;
                    var startComparable = shiftDateByYears(new Date(endComparable), -1).getTime();
                    return buildComparableRange(startComparable, endComparable, axisInfo);
                }
            },
            {
                key: '3l',
                label: '3l',
                calc: function () {
                    var endComparable = axisInfo.max.comparable;
                    var startComparable = shiftDateByYears(new Date(endComparable), -3).getTime();
                    return buildComparableRange(startComparable, endComparable, axisInfo);
                }
            },
            {
                key: '5l',
                label: '5l',
                calc: function () {
                    var endComparable = axisInfo.max.comparable;
                    var startComparable = shiftDateByYears(new Date(endComparable), -5).getTime();
                    return buildComparableRange(startComparable, endComparable, axisInfo);
                }
            },
            {
                key: 'max',
                label: 'max',
                calc: function () {
                    return {
                        startValue: axisInfo.min.raw,
                        endValue: axisInfo.max.raw
                    };
                }
            }
        ];

        rangeConfigs.forEach(function (config) {
            var $button = $('<button type="button"/>')
                .addClass('btn btn-default btn-sm')
                .attr('data-range', config.key)
                .text(config.label)
                .on('click', function (event) {
                    event.preventDefault();
                    var range = config.calc();
                    if (!range) {
                        return;
                    }
                    rangeData.setActive(config.key);
                    $el.data('mfChartPendingRange', config.key);
                    chart.dispatchAction($.extend({ type: 'dataZoom' }, range));
                });

            rangeData.buttons.push({ key: config.key, $el: $button });
            $group.append($button);
        });

        $el.before($container);
        $el.data('mfChartRangeButtons', rangeData);
        rangeData.setActive('max');
    }

    function findModeByKey(modes, key) {
        if (!modes || !modes.length) {
            return null;
        }
        for (var i = 0; i < modes.length; i++) {
            var mode = modes[i];
            if (mode && mode.key === key) {
                return mode;
            }
        }
        return null;
    }

    function buildModePayload(basePayload, requestedKey) {
        if (!basePayload) {
            return null;
        }

        var payload = $.extend(true, {}, basePayload);
        var modes = $.isArray(basePayload.modes) ? basePayload.modes : null;
        delete payload.modes;
        delete payload.defaultMode;

        if (!modes || !modes.length) {
            return { payload: payload, key: null };
        }

        var modeKey = requestedKey;
        var mode = modeKey !== undefined && modeKey !== null ? findModeByKey(modes, modeKey) : null;
        if (!mode && basePayload.defaultMode) {
            modeKey = basePayload.defaultMode;
            mode = findModeByKey(modes, modeKey);
        }
        if (!mode) {
            mode = modes[0];
            modeKey = mode && mode.key !== undefined ? mode.key : null;
        }

        if (mode) {
            if (mode.title !== undefined) {
                payload.title = mode.title;
            }
            if (mode.unit !== undefined) {
                payload.unit = mode.unit;
            } else if (basePayload.unit !== undefined) {
                payload.unit = basePayload.unit;
            } else {
                delete payload.unit;
            }
            if (mode.axis !== undefined) {
                payload.axis = mode.axis;
            } else if (basePayload.axis !== undefined) {
                payload.axis = basePayload.axis;
            } else {
                delete payload.axis;
            }
            if (mode.categories !== undefined) {
                payload.categories = mode.categories;
            } else if (payload.axis !== 'category') {
                delete payload.categories;
            }
            if (mode.series !== undefined) {
                payload.series = $.extend(true, [], mode.series || []);
            } else {
                payload.series = [];
            }
        }

        if (payload.axis !== 'category') {
            delete payload.categories;
        }

        return { payload: payload, key: modeKey };
    }

    function buildOptions(response, meta) {
        var unit = response.unit || (meta ? meta.unit : '');
        var titleText = (meta && meta.title) || response.title || '';
        var isCategoryAxis = response.axis === 'category';
        var categories = isCategoryAxis && $.isArray(response.categories) ? response.categories : [];
        var tooltipFormatter = function (params) {
            if (!params || !params.length) {
                return '';
            }
            var header = params[0].axisValueLabel || params[0].axisValue;
            var lines = params.map(function (item) {
                var val = item.data && $.isArray(item.data) ? item.data[1] : item.value;
                return item.marker + ' ' + item.seriesName + ': ' + formatValue(val, unit);
            });
            return header + '<br />' + lines.join('<br />');
        };

        var builtSeries = buildSeries(response.series, unit);
        var hasBarSeries = builtSeries.some(function (serie) {
            return serie.type === 'bar';
        });

        var options = {
            tooltip: {
                trigger: 'axis',
                formatter: tooltipFormatter,
                axisPointer: {
                    type: hasBarSeries ? 'shadow' : 'line'
                }
            },
            grid: {
                left: 50,
                right: 20,
                bottom: titleText ? 80 : (isCategoryAxis ? 40 : 60),
                top: titleText ? 60 : 30
            },
            xAxis: isCategoryAxis ? {
                type: 'category',
                boundaryGap: hasBarSeries,
                data: categories
            } : {
                type: 'time',
                boundaryGap: false
            },
            yAxis: {
                type: 'value',
                axisLabel: {
                    formatter: function (value) {
                        return formatValue(value, unit);
                    }
                }
            },
            series: builtSeries,
            dataZoom: isCategoryAxis ? [] : [
                {
                    type: 'inside',
                    throttle: 50
                },
                {
                    type: 'slider',
                    height: 20,
                    bottom: 10
                }
            ]
        };

        if (titleText) {
            options.title = {
                text: titleText,
                left: 'center',
                textStyle: {
                    fontSize: 14,
                    fontWeight: 'normal'
                }
            };
        }

        if (unit === '%') {
            options.yAxis.axisLabel.margin = 12;
        }

        options.mfCategoryAxis = isCategoryAxis;

        return options;
    }

    function showError($el, message) {
        disposeChart($el);
        $el.empty().append($('<div/>').addClass('chart-error').text(message));
    }

    function setupModeControls($el, basePayload, activeKey) {
        var modes = basePayload && $.isArray(basePayload.modes) ? basePayload.modes : null;
        var existing = $el.data('mfChartModeControls');
        if (existing && existing.container) {
            existing.container.remove();
        }
        $el.removeData('mfChartModeControls');

        if (!modes || modes.length <= 1) {
            return;
        }

        var $container = $('<div/>').addClass('fund-chart-mode-controls text-right');
        var $group = $('<div/>').addClass('btn-group btn-group-sm').attr('role', 'group');
        $container.append($group);

        var data = {
            container: $container,
            buttons: [],
            setActive: function (key) {
                for (var i = 0; i < data.buttons.length; i++) {
                    var button = data.buttons[i];
                    if (key !== null && key !== undefined && button.key === key) {
                        button.$el.removeClass('btn-default').addClass('btn-primary');
                    } else {
                        button.$el.removeClass('btn-primary').addClass('btn-default');
                    }
                }
            }
        };

        modes.forEach(function (mode) {
            var key = mode && mode.key !== undefined ? mode.key : '';
            var label = mode && mode.label ? mode.label : (key || 'Tryb');
            var $btn = $('<button type="button"/>')
                .addClass('btn btn-default btn-sm')
                .attr('data-mode', key)
                .text(label)
                .on('click', function (event) {
                    event.preventDefault();
                    applyChartMode($el, key);
                });
            data.buttons.push({ key: key, $el: $btn });
            $group.append($btn);
        });

        $el.before($container);
        $el.data('mfChartModeControls', data);
        data.setActive(activeKey);
    }

    function renderChartContent($el, basePayload, meta, requestedModeKey) {
        if (typeof echarts === 'undefined') {
            showError($el, 'Biblioteka wykresA3w nie zostaA?a zaA?adowana.');
            return;
        }

        disposeChart($el);

        var modeResult = buildModePayload(basePayload, requestedModeKey);
        if (!modeResult || !modeResult.payload) {
            showError($el, 'Brak danych do wyA?wietlenia.');
            return;
        }

        var payload = modeResult.payload;
        var activeModeKey = modeResult.key;

        var options = buildOptions(payload, meta);
        if (!options.series.length) {
            showError($el, 'Brak danych do wyA?wietlenia.');
            return;
        }

        var isCategoryAxis = !!options.mfCategoryAxis;
        if (options.hasOwnProperty('mfCategoryAxis')) {
            delete options.mfCategoryAxis;
        }

        $el.empty();

        // Clone raw data BEFORE any transformation
        var rawSeriesData = cloneSeriesData(options.series);
        var rebaseMode = !!payload.rebase;
        var lastZoomSignature = null;
        var isRebased = false;

        // If rebase mode, convert raw prices ‚?? percentages before initial render
        var originalSeriesData;
        if (rebaseMode) {
            var initialRebased = buildRebasedSeriesData(rawSeriesData, null, true);
            originalSeriesData = initialRebased;
            for (var si = 0; si < options.series.length && si < initialRebased.length; si++) {
                options.series[si].data = initialRebased[si];
            }
        } else {
            originalSeriesData = rawSeriesData;
        }

        var chart = echarts.init($el[0]);
        chart.setOption(options);

        if (!isCategoryAxis) {
            // Range controls use the raw data for axis info (dates match regardless of rebasing)
            setupRangeControls($el, chart, rawSeriesData);

            var zoomHandler = function (event) {
                if (!event) {
                    return;
                }
                var zoomEvent = event;
                if (event.batch && event.batch.length) {
                    for (var i = 0; i < event.batch.length; i++) {
                        if (event.batch[i] && (event.batch[i].start !== undefined || event.batch[i].startValue !== undefined)) {
                            zoomEvent = event.batch[i];
                            break;
                        }
                    }
                    if (zoomEvent === event && event.batch.length) {
                        zoomEvent = event.batch[0];
                    }
                }

                if (!zoomEvent) {
                    return;
                }

                var rangeData = $el.data('mfChartRangeButtons');
                var pendingRange = $el.data('mfChartPendingRange');

                var signature = [
                    zoomEvent.start !== undefined ? zoomEvent.start : '',
                    zoomEvent.end !== undefined ? zoomEvent.end : '',
                    zoomEvent.startValue !== undefined ? zoomEvent.startValue : '',
                    zoomEvent.endValue !== undefined ? zoomEvent.endValue : ''
                ].join('|');

                if (signature === lastZoomSignature) {
                    return;
                }
                lastZoomSignature = signature;

                if (isFullRangeZoom(zoomEvent, rawSeriesData[0])) {
                    if (rangeData && rangeData.setActive) {
                        rangeData.setActive('max');
                    }
                    $el.removeData('mfChartPendingRange');
                    if (isRebased) {
                        chart.setOption({
                            series: originalSeriesData.map(function (data) { return { data: data }; }),
                            yAxis: { min: null }
                        }, false, false);
                        isRebased = false;
                    }
                    return;
                }

                if (pendingRange && rangeData && rangeData.setActive) {
                    rangeData.setActive(pendingRange);
                } else if (rangeData && rangeData.setActive) {
                    rangeData.setActive(null);
                }
                $el.removeData('mfChartPendingRange');

                // For rebase mode: always rebase from RAW prices ‚?? correct percentages
                // For non-rebase: subtract from the original data
                var sourceData = rebaseMode ? rawSeriesData : originalSeriesData;
                var startAxisValue = computeStartAxisValue(zoomEvent, sourceData[0]);
                var rebasedSeries = buildRebasedSeriesData(sourceData, startAxisValue, rebaseMode);

                chart.setOption({
                    series: rebasedSeries.map(function (data) { return { data: data }; }),
                    yAxis: {
                        min: function (value) {
                            return value.min > 0 ? 0 : value.min;
                        }
                    }
                }, false, false);

                isRebased = true;
            };

            chart.on('dataZoom', zoomHandler);
            $el.data('mfChartZoom', zoomHandler);
        } else {
            $el.removeData('mfChartRangeButtons');
            $el.removeData('mfChartPendingRange');
        }

        var handlerId = 'fundChartResize' + (++chartUid);
        var resizeHandler = function () {
            chart.resize();
        };

        window.addEventListener('resize', resizeHandler);
        $el.data('mfChartInstance', chart);
        $el.data('mfChartResize', resizeHandler);
        $el.data('mfChartResizeId', handlerId);
        $el.data('mfChartCurrentMode', activeModeKey);

        var modeControls = $el.data('mfChartModeControls');
        if (modeControls && modeControls.setActive) {
            modeControls.setActive(activeModeKey);
        }
    }

    function applyChartMode($el, modeKey) {
        var basePayload = $el.data('mfChartBasePayload');
        var meta = $el.data('mfChartMeta') || {};
        if (!basePayload) {
            return;
        }
        renderChartContent($el, basePayload, meta, modeKey);
    }

    function renderChart($el, response, meta) {
        if (typeof echarts === 'undefined') {
            showError($el, 'Biblioteka wykresA3w nie zostaA?a zaA?adowana.');
            return;
        }

        var basePayload = $.extend(true, {}, response || {});
        var datasetMeta = meta || {};

        $el.data('mfChartBasePayload', basePayload);
        $el.data('mfChartMeta', datasetMeta);

        setupModeControls($el, basePayload, basePayload.defaultMode || null);

        renderChartContent($el, basePayload, datasetMeta, basePayload.defaultMode || null);
    }

    function loadChart($el, url, meta) {
        if (!$el || !$el.length) {
            return;
        }

        var datasetMeta = $.extend({}, meta || {}, {
            title: (meta && meta.title) || $el.data('chart-title'),
            type: (meta && meta.type) || $el.data('chart-type')
        });

        var source = url || $el.data('chart-source');
        var inlinePayload = $el.attr('data-chart-payload');

        if (inlinePayload && inlinePayload.length) {
            $el.removeClass('chart-error').text('AÅadowanie wykresu...');
            var payload;
            try {
                payload = JSON.parse(inlinePayload);
            } catch (err) {
                showError($el, 'NieprawidA?owe dane wykresu.');
                return;
            }

            if (payload && payload.status === 'ok') {
                renderChart($el, payload, datasetMeta);
            } else {
                showError($el, (payload && payload.message) || 'Brak danych do wyA?wietlenia.');
            }
            return;
        }

        if (!source) {
            showError($el, 'Brak AorA3dA?a danych.');
            return;
        }

        $el.removeClass('chart-error').text('AÅadowanie wykresu...');

        $.getJSON(source)
            .done(function (response) {
                if (response && response.status === 'ok') {
                    renderChart($el, response, datasetMeta);
                } else {
                    showError($el, (response && response.message) || 'Brak danych do wyA?wietlenia.');
                }
            })
            .fail(function () {
                showError($el, 'Nie udaA?o siƒ? wczytaƒ? wykresu.');
            });
    }

    $(function () {
        $('.fund-chart').each(function () {
            loadChart($(this));
        });

        $(document).on('shown.bs.tab', 'a[data-toggle="tab"], a[data-bs-toggle="tab"]', function (e) {
            var targetSelector = $(e.target).attr('href');
            if (!targetSelector) {
                return;
            }
            var $target = $(targetSelector);
            if (!$target.length) {
                return;
            }
            $target.find('.fund-chart').each(function () {
                var $chartEl = $(this);
                var chartInstance = $chartEl.data('mfChartInstance');
                if (chartInstance) {
                    chartInstance.resize();
                } else {
                    loadChart($chartEl);
                }
            });
        });
    });

    window.mfCharts = {
        load: function (target, url, meta) {
            var $el = target instanceof $ ? target : $(target);
            if ($el.length) {
                loadChart($el, url, meta || {});
            }
        },
        refresh: function (selector) {
            $(selector).each(function () {
                loadChart($(this));
            });
        }
    };

})(jQuery, window);

